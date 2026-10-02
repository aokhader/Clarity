"""Command-line entry point: `python -m app.cli {auth,sync,digest,seed-dev,reset}`."""

import argparse
import logging
import shutil
import sys
from collections.abc import Callable

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


def _seed_dev(_args: argparse.Namespace) -> int:
    # Imported here so the application never depends on test code outside this command.
    from tests.fixtures.synthetic_matter import load_synthetic_matter

    init_db()
    with get_sessionmaker()() as session:
        matter_id = load_synthetic_matter(session)
        session.commit()
    print(f"Loaded the synthetic matter as matter {matter_id}: /matters/{matter_id}")
    return 0


def _not_built(milestone: str) -> Command:
    def run(_args: argparse.Namespace) -> int:
        print(
            f"Not built yet: arrives in {milestone} (see docs/tracks/a-pipeline.md).",
            file=sys.stderr,
        )
        return 2

    return run


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(
        prog="python -m app.cli", description="Clarity pipeline."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "auth", help="one-time Clio OAuth; stores tokens in the database"
    ).set_defaults(run=_not_built("A1"))
    commands.add_parser(
        "sync", help="pull the matter from Clio into sources"
    ).set_defaults(run=_not_built("A1"))
    commands.add_parser(
        "digest", help="pages -> facts -> brief (cached, incremental)"
    ).set_defaults(run=_not_built("A2"))
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
