"""Write the synced matter's raw Clio records and page text to data/raw-export.json.

That file is the export tests/no_literals.test.mjs derives its forbidden terms
from, so the case data the repository must never contain is read from the case
itself at check time and never written into the repository. It lands in the
data directory, which is gitignored. Run by scripts/check.sh.

The synthetic matter from `cli seed-dev` is left out: its text is invented and
committed on purpose in backend/tests/fixtures/synthetic_matter.py, so deriving
terms from it would flag the fixture itself. A database that holds only the
synthetic matter exits with NOTHING_SYNCED, which check.sh reports as SKIPPED.
"""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.config import get_settings
from tests.fixtures.synthetic_matter import MATTER_ID as SYNTHETIC_MATTER_ID

NOTHING_SYNCED = 3


def main() -> int:
    settings = get_settings()
    database = settings.database_path
    if not database.exists():
        print(
            f"No database at {database}: run `python -m app.cli sync` first.",
            file=sys.stderr,
        )
        return 1
    with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as connection:
        records = [
            json.loads(raw)
            for (raw,) in connection.execute(
                "SELECT raw_json FROM sources WHERE matter_id != ?",
                (SYNTHETIC_MATTER_ID,),
            )
        ]
        pages = [
            {"text": text}
            for (text,) in connection.execute(
                "SELECT pages.text FROM pages JOIN sources ON sources.id = pages.source_id"
                " WHERE pages.text IS NOT NULL AND sources.matter_id != ?",
                (SYNTHETIC_MATTER_ID,),
            )
        ]
    if not records:
        print(
            "Only the synthetic matter is in the database: no synced matter to derive terms from."
        )
        return NOTHING_SYNCED
    target = settings.data_dir / "raw-export.json"
    target.write_text(
        json.dumps({"records": records, "pages": pages}), encoding="utf-8"
    )
    print(
        f"Exported {len(records)} records and {len(pages)} pages of text to {target.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
