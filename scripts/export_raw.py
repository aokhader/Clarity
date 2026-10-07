"""Write the synced matter's raw Clio records and page text to data/raw-export.json.

That file is the export tests/no_literals.test.mjs derives its forbidden terms
from, so the case data the repository must never contain is read from the case
itself at check time and never written into the repository. It lands in the
data directory, which is gitignored. Run by scripts/check.sh.
"""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.config import get_settings  # noqa: E402


def main() -> int:
    settings = get_settings()
    database = settings.database_path
    if not database.exists():
        print(f"No database at {database}: run `python -m app.cli sync` first.", file=sys.stderr)
        return 1
    with sqlite3.connect(database) as connection:
        records = [json.loads(raw) for (raw,) in connection.execute("SELECT raw_json FROM sources")]
        pages = [{"text": text} for (text,) in connection.execute("SELECT text FROM pages WHERE text IS NOT NULL")]
    target = settings.data_dir / "raw-export.json"
    target.write_text(json.dumps({"records": records, "pages": pages}), encoding="utf-8")
    print(f"Exported {len(records)} records and {len(pages)} pages of text to {target.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
