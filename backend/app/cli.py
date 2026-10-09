"""Command-line entry point: `python -m app.cli {auth,sync,digest,reextract,upgrade-schema,
seed-dev,reset}`."""

import argparse
import json
import logging
import shutil
import sqlite3
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from app.config import get_settings
from app.db import dispose_engine, get_sessionmaker, init_db

# Everything a data directory may hold. `reset` refuses to delete a directory with
# anything else in it, so a mistyped DATA_DIR cannot wipe unrelated files.
_DATA_DIR_ENTRIES = {
    "app.db",
    "app.db-wal",
    "app.db-shm",
    "app.db-journal",
    "files",
    "pages",
}

Command = Callable[[argparse.Namespace], int]


def _reset(_args: argparse.Namespace) -> int:
    data_dir = get_settings().data_dir
    if not data_dir.exists():
        print(f"Nothing to reset: {data_dir} does not exist.")
        return 0
    unexpected = sorted(
        p.name for p in data_dir.iterdir() if p.name not in _DATA_DIR_ENTRIES
    )
    if unexpected:
        print(
            f"Refusing to delete {data_dir}: unexpected entries {unexpected}.",
            file=sys.stderr,
        )
        return 1
    dispose_engine()
    try:
        shutil.rmtree(data_dir)
    except OSError as error:
        print(
            f"Could not delete {data_dir} ({error}). Stop the API server first.",
            file=sys.stderr,
        )
        return 1
    print(f"Deleted {data_dir}.")
    return 0


def _auth(args: argparse.Namespace) -> int:
    from app.clio import oauth

    # Before the database or any URL: an unset client id would print client_id=None.
    missing = oauth.missing_client_settings()
    if missing:
        print(
            f"Clio is not set up: set {' and '.join(missing)} in .env, from the "
            "developer app registered with Clio (docs/clio-api.md).",
            file=sys.stderr,
        )
        return 1
    init_db()
    state = oauth.new_state()
    print("Open this URL, sign in to Clio, and approve read access:\n")
    print(oauth.authorize_url(state))
    try:
        if args.manual:
            print("\nAfter approving, copy the full address your browser was sent to")
            print("(it starts with the redirect URI) and paste it here:")
            code = oauth.code_from_redirect_url(input("> "), state)
        else:
            print(
                f"\nWaiting for the redirect on {get_settings().clio_redirect_uri} ..."
            )
            code = oauth.wait_for_code(state)
        with get_sessionmaker()() as session:
            oauth.exchange_code(session, code)
    except (oauth.ClioNotAuthorized, OSError) as error:
        print(f"Auth failed: {error}", file=sys.stderr)
        return 1
    print("Clio connected. Tokens stored in the database.")
    return 0


def _sync(args: argparse.Namespace) -> int:
    from app.clio.client import ClioClient, ClioError
    from app.clio.oauth import ClioNotAuthorized, TokenStore
    from app.clio.sync import MatterNotFound, resolve_matter_id, sync_matter

    init_db()
    with get_sessionmaker()() as session:
        tokens = TokenStore(session)
        client = ClioClient(tokens.access_token, tokens.refresh)
        try:
            matter_id = resolve_matter_id(
                client, get_settings().clio_matter_query, args.matter_id
            )
            run = sync_matter(session, client, matter_id)
        except (ClioNotAuthorized, MatterNotFound, ClioError) as error:
            print(f"Sync failed: {error}", file=sys.stderr)
            return 1
        finally:
            client.close()
        print(f"Matter {matter_id} synced.")
        print(json.dumps(run.stats_json, indent=2))
        return 1 if run.error else 0


def _digest(args: argparse.Namespace) -> int:
    from app.digest.run import NoSyncedMatter, run_digest, synced_matter_id

    init_db()
    with get_sessionmaker()() as session:
        try:
            matter_id = synced_matter_id(session, args.matter_id)
        except NoSyncedMatter as error:
            print(str(error), file=sys.stderr)
            return 1
        if args.pages_only:
            # PyMuPDF only: no model, and no digest run row, since nothing is digested.
            from app.digest.pages import build_pages

            print(json.dumps(dict(build_pages(session, matter_id)), indent=2))
            return 0
        run = run_digest(session, matter_id, retry_failed=args.retry_failed)
        print(json.dumps(run.stats_json, indent=2))
        if run.error:
            print(f"Digest error: {run.error}", file=sys.stderr)
            return 1
        return 0


def _reextract(args: argparse.Namespace) -> int:
    from app.digest.reextract import (
        NotRereadable,
        describe,
        estimate,
        mark_unread,
        select_units,
    )
    from app.digest.run import NoSyncedMatter, run_digest, synced_matter_id

    init_db()
    with get_sessionmaker()() as session:
        try:
            matter_id = synced_matter_id(session, args.matter_id)
            selection = select_units(
                session,
                matter_id,
                pages=[_page_key(value) for value in args.page],
                records=args.record,
                fact_ids=args.behind_fact,
                kinds=args.behind_kind,
            )
        except (NoSyncedMatter, NotRereadable, ValueError) as error:
            print(str(error), file=sys.stderr)
            return 1
        cost = estimate(session, selection, brief=not args.keep_brief)
        pages, records = len(selection.pages), len(selection.records)
        print(
            f"Selected {_count(pages, 'page')} and {_count(records, 'record')}, "
            f"holding {_count(cost.facts_held, 'fact')}:"
        )
        for line in describe(session, selection):
            print(f"  {line}")
        price = f"about ${cost.usd:.2f}" if cost.usd is not None else "cost unknown"
        then = (
            "scoring the new facts; the brief is kept"
            if args.keep_brief
            else "scoring the new facts and one brief"
        )
        print(
            f"At most {_count(cost.extraction_calls, 'extraction call')}, then "
            f"{then}: {price}, at the average recorded per call."
        )
        if args.dry_run or not (pages or records):
            return 0
        mark_unread(selection)
        session.commit()
        run = run_digest(session, matter_id, write_brief=not args.keep_brief)
        print(json.dumps(run.stats_json, indent=2))
        if run.error:
            print(f"Digest error: {run.error}", file=sys.stderr)
            return 1
        return 0


def _page_key(value: str) -> tuple[int, int]:
    source_id, _, page_no = value.partition(":")
    if not (source_id.isdigit() and page_no.isdigit()):
        raise ValueError(f"--page takes SOURCE_ID:PAGE_NO, not {value!r}")
    return int(source_id), int(page_no)


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


class BackupFailed(Exception):
    pass


def _upgrade_schema(_args: argparse.Namespace) -> int:
    """Back the database up, then rebuild tables whose enum constraints are out of date.

    Only this command and seed-dev upgrade; the API, sync and digest never do it on
    their own, since a rebuild should run with nothing else writing.
    """
    from app.db import SchemaUpgradeFailed, upgrade_schema

    settings = get_settings()
    database = settings.database_path
    if not database.exists():
        print(f"Nothing to upgrade: no database at {database}.")
        return 0
    try:
        backup = _backup_database(database, settings.backups_dir)
    except (BackupFailed, sqlite3.Error) as error:
        print(f"Upgrade not started: the backup failed ({error}).", file=sys.stderr)
        return 1
    print(f"Backed up {database} to {backup} (integrity ok).")
    try:
        rebuilt = upgrade_schema()
    except (SchemaUpgradeFailed, sqlite3.Error) as error:
        print(
            f"Upgrade failed and was rolled back ({error}). Backup: {backup}",
            file=sys.stderr,
        )
        return 1
    if rebuilt:
        print(f"Rebuilt with the current constraints: {', '.join(rebuilt)}.")
    else:
        print("Nothing to upgrade: every table allows every value the code has.")
    return 0


def _backup_database(database: Path, directory: Path) -> Path:
    """A consistent copy through SQLite's backup API, checked before it is trusted."""
    directory.mkdir(parents=True, exist_ok=True)
    stamp = f"{datetime.now().astimezone():%Y%m%d-%H%M%S}"
    target = directory / f"app-{stamp}-pre-upgrade.db"
    attempt = 1
    while target.exists():
        attempt += 1
        target = directory / f"app-{stamp}-pre-upgrade-{attempt}.db"
    source = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    copy = sqlite3.connect(target)
    try:
        source.backup(copy)
        # A single file: no WAL or shared-memory files left beside the backup.
        copy.execute("PRAGMA journal_mode=DELETE")
        result = copy.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        copy.close()
        source.close()
    if result != "ok":
        raise BackupFailed(f"{target} failed its integrity check: {result}")
    return target


def _seed_dev(_args: argparse.Namespace) -> int:
    # Imported here so the application never depends on test code outside this command.
    from app.db import upgrade_schema
    from tests.fixtures.synthetic_matter import load_synthetic_matter

    # A development database made before a new fact kind refuses that kind until its
    # table is rebuilt. upgrade_schema backs it up beside itself when it rebuilds.
    rebuilt = upgrade_schema()
    if rebuilt:
        print(f"Upgraded the database first: rebuilt {', '.join(rebuilt)}.")
    init_db()
    with get_sessionmaker()() as session:
        matter_id = load_synthetic_matter(session)
        session.commit()
    print(f"Loaded the synthetic matter as matter {matter_id}: /matters/{matter_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    # httpx logs every request at INFO, which buries the stage summaries.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(
        prog="python -m app.cli", description="Clarity pipeline."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    auth = commands.add_parser(
        "auth", help="one-time Clio OAuth; stores tokens in the database"
    )
    auth.add_argument(
        "--manual",
        action="store_true",
        help="paste the redirected URL instead of listening for it",
    )
    auth.set_defaults(run=_auth)
    sync = commands.add_parser("sync", help="pull the matter from Clio into sources")
    sync.add_argument(
        "--matter-id", type=int, help="skip the search and use this Clio matter id"
    )
    sync.set_defaults(run=_sync)
    digest = commands.add_parser(
        "digest", help="pages -> facts -> brief (cached, incremental)"
    )
    digest.add_argument("--matter-id", type=int)
    digest.add_argument(
        "--retry-failed",
        action="store_true",
        help="ask the model again for inputs whose last call failed",
    )
    digest.add_argument(
        "--pages-only",
        action="store_true",
        help="split documents into page text and images only; no model call",
    )
    digest.set_defaults(run=_digest)
    reextract = commands.add_parser(
        "reextract",
        help="read chosen pages and records again with the current prompts",
    )
    reextract.add_argument("--matter-id", type=int)
    reextract.add_argument(
        "--page", action="append", default=[], help="SOURCE_ID:PAGE_NO of a document"
    )
    reextract.add_argument(
        "--record",
        action="append",
        type=int,
        default=[],
        help="a note or email source id",
    )
    reextract.add_argument(
        "--behind-fact",
        action="append",
        type=int,
        default=[],
        help="the unit a fact came from",
    )
    reextract.add_argument(
        "--behind-kind",
        action="append",
        default=[],
        help="every unit with a fact of this kind",
    )
    reextract.add_argument(
        "--dry-run",
        action="store_true",
        help="list the selection and its cost; change nothing",
    )
    reextract.add_argument(
        "--keep-brief",
        action="store_true",
        help="leave the stored brief as it is; the next digest writes it",
    )
    reextract.set_defaults(run=_reextract)
    commands.add_parser(
        "upgrade-schema",
        help="back up the database, then rebuild tables a new enum value would break;"
        " stop the API first",
    ).set_defaults(run=_upgrade_schema)
    commands.add_parser(
        "seed-dev", help="load the invented matter for development without Clio"
    ).set_defaults(run=_seed_dev)
    commands.add_parser(
        "reset", help="drop the database and the data directory"
    ).set_defaults(run=_reset)
    args = parser.parse_args(argv)
    command: Command = args.run
    return command(args)


if __name__ == "__main__":
    sys.exit(main())
