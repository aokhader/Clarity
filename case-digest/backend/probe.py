"""Quick Clio explorer for discovering endpoints and field names (read-only).

Examples:
    python -m backend.probe matters.json --fields "id,display_number,description"
    python -m backend.probe notes.json --param matter_id=123 --param type=Matter --fields "id,subject,detail"
"""
import argparse
import json

from .clio_client import ClioHTTPError, ClioReadOnlyClient


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--fields", default=None)
    parser.add_argument("--param", action="append", default=[], help="key=value, repeatable")
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()

    params = dict(p.split("=", 1) for p in args.param)
    params["limit"] = args.limit
    if args.fields:
        params["fields"] = args.fields
    try:
        print(json.dumps(ClioReadOnlyClient().get(args.path, params), indent=2)[:8000])
    except ClioHTTPError as exc:
        print(f"HTTP {exc.status}\n{exc.body[:2000]}")


if __name__ == "__main__":
    main()
