"""One command to connect this project to Clio and confirm it works.

    python -m backend.connect                 # set up credentials, verify, list matters
    python -m backend.connect --ingest        # ...then pull the matter straight away
    python -m backend.connect --query <name>  # pick the matter by search text

Steps:
  1. If no credentials exist, asks you to paste an access token (or OAuth app ID/secret) and saves them to .env
  2. Runs the OAuth browser flow if you chose OAuth and have no token yet
  3. Verifies the token by asking Clio who you are (read-only)
  4. Lists the matters in the account and picks the one to use
"""
import argparse
import getpass
import importlib
import sys

from . import config


def _write_env(updates: dict) -> None:
    env_path = config.ROOT / ".env"
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    keys_done = set()
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in updates:
            lines[i] = f"{key}={updates[key]}"
            keys_done.add(key)
    for key, value in updates.items():
        if key not in keys_done:
            lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n")


def _reload_config() -> None:
    import os
    from dotenv import load_dotenv
    load_dotenv(config.ROOT / ".env", override=True)
    for mod in ("backend.config", "backend.auth", "backend.clio_client"):
        if mod in sys.modules:
            importlib.reload(sys.modules[mod])
    os.environ.setdefault("CLIO_BASE_URL", config.CLIO_BASE_URL)


def ensure_credentials() -> None:
    from . import config as cfg
    if cfg.CLIO_ACCESS_TOKEN or cfg.TOKEN_FILE.exists():
        return
    if cfg.CLIO_CLIENT_ID and cfg.CLIO_CLIENT_SECRET:
        from .auth import run_oauth_flow
        print("Found OAuth app credentials; opening Clio consent in your browser...")
        run_oauth_flow()
        return

    print("No Clio credentials yet.\n")
    print("  [1] Paste an access token (fastest, if the Swans setup app or Clio gave you one)")
    print("  [2] Use an OAuth app (Clio Settings > Developer Applications; redirect URI "
          f"{cfg.CLIO_REDIRECT_URI})")
    choice = input("\nChoose 1 or 2: ").strip()
    region = input(f"Clio base URL [{cfg.CLIO_BASE_URL}]: ").strip() or cfg.CLIO_BASE_URL
    if choice == "1":
        token = getpass.getpass("Access token (hidden): ").strip()
        _write_env({"CLIO_BASE_URL": region, "CLIO_ACCESS_TOKEN": token})
        _reload_config()
    else:
        client_id = input("Client ID: ").strip()
        secret = getpass.getpass("Client secret (hidden): ").strip()
        _write_env({"CLIO_BASE_URL": region, "CLIO_CLIENT_ID": client_id, "CLIO_CLIENT_SECRET": secret})
        _reload_config()
        from .auth import run_oauth_flow
        run_oauth_flow()
    print("Saved to .env (git-ignored).\n")


def verify(client) -> dict:
    from .clio_client import ClioHTTPError
    try:
        me = client.get("users/who_am_i.json", {"fields": "id,name,email"})["data"]
    except ClioHTTPError as exc:
        if exc.status == 401:
            raise SystemExit("Clio rejected the token (401). It may be expired or for another region "
                             "(check CLIO_BASE_URL).")
        raise
    print(f"Connected to Clio as {me.get('name')} <{me.get('email')}>  ({client.base_url})")
    return me


def main(argv=None):
    parser = argparse.ArgumentParser(description="Connect to Clio and verify access (read-only).")
    parser.add_argument("--query", help="search text to pick the matter")
    parser.add_argument("--ingest", action="store_true", help="ingest the chosen matter after connecting")
    parser.add_argument("--skip-docs", action="store_true")
    args = parser.parse_args(argv)

    ensure_credentials()
    from .clio_client import ClioReadOnlyClient
    from .ingest import list_matters, print_matters

    client = ClioReadOnlyClient()
    verify(client)

    matters = list_matters(client, args.query)
    print(f"\nMatters visible{' for ' + repr(args.query) if args.query else ''}: {len(matters)}")
    print_matters(matters)
    if not matters:
        print("\nNo matters yet. If the Swans setup app is still loading the case, wait and re-run.")
        return 1

    if len(matters) == 1:
        matter_id = str(matters[0]["id"])
    else:
        matter_id = input("\nMatter id to use: ").strip()
    _write_env({"CLIO_MATTER_ID": matter_id})
    print(f"\nSaved CLIO_MATTER_ID={matter_id} to .env")

    if args.ingest:
        from . import db
        from .ingest import ingest
        conn = db.connect()
        db.init_db(conn)
        counts = ingest(client, conn, matter_id, skip_docs=args.skip_docs)
        print("\nSynced:")
        for key, value in sorted(counts.items()):
            print(f"  {key:<20} {value}")
    else:
        print("Next: python -m backend.ingest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
