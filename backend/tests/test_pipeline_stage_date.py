"""The case-stage fact is dated by when the stage changed, never by the matter's last edit.

The stage fact took `updated_at`, the Clio matter record's last edit of any kind, so a
chat answer gave that edit as the day the case moved to its stage (critic Pass 6, #2).
Clio's Matter carries `matter_stage_updated_at`, which the sync now requests.
"""

from datetime import date
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clio.client import ClioClient
from app.clio.sync import MATTER_FIELDS, sync_matter
from app.digest.matter_fields import stage_facts
from app.models import Source, SourceType
from app.schemas import CaseStage

MATTER = 1
STAGE_FIELD = "matter_stage_updated_at"


def _matter(raw: dict) -> Source:
    return Source(
        matter_id=MATTER, clio_type=SourceType.MATTER, clio_id="1", raw_json=raw
    )


def test_the_stage_fact_carries_the_day_the_stage_changed() -> None:
    matter = _matter(
        {
            "matter_stage": {"name": "Invented stage"},
            "matter_stage_updated_at": "2021-03-04T09:30:00-08:00",
            "updated_at": "2022-07-08T10:00:00-07:00",
        }
    )

    [fact] = stage_facts(matter, CaseStage.TREATING)

    assert fact.event_date == date(2021, 3, 4)


def test_without_a_stage_change_date_the_stage_fact_is_undated() -> None:
    matter = _matter(
        {
            "matter_stage": {"name": "Invented stage"},
            "updated_at": "2022-07-08T10:00:00-07:00",
        }
    )

    [fact] = stage_facts(matter, CaseStage.TREATING)

    assert fact.event_date is None


def test_an_inferred_stage_is_undated_too() -> None:
    matter = _matter({"status": "Open", "updated_at": "2022-07-08T10:00:00-07:00"})

    [fact] = stage_facts(matter, CaseStage.INTAKE)

    assert fact.event_date is None


def test_the_sync_requests_the_stage_change_date() -> None:
    assert STAGE_FIELD in MATTER_FIELDS[0].split(",")


def test_a_rejected_stage_date_falls_back_to_the_full_list_without_it(
    data_dir: Path, session: Session
) -> None:
    """Clio answers an unknown field name with a 400. Losing the stage date must not
    cost the custom fields and the stage, which the shortest list leaves out."""
    asked: list[str] = []

    def clio(request: httpx.Request) -> httpx.Response:
        path = request.url.path.split("/api/v4/", 1)[-1]
        if path == f"matters/{MATTER}.json":
            fields = request.url.params["fields"]
            asked.append(fields)
            if STAGE_FIELD in fields:
                return httpx.Response(400, json={"error": {"message": "bad field"}})
            raw = {
                "id": MATTER,
                "etag": "m",
                "matter_stage": {"name": "Invented stage"},
                "custom_field_values": [],
            }
            return httpx.Response(200, json={"data": raw})
        return httpx.Response(200, json={"data": [], "meta": {"paging": {}}})

    client = ClioClient(
        get_token=lambda: "token",
        transport=httpx.MockTransport(clio),
        sleep=lambda _s: None,
    )
    run = sync_matter(session, client, MATTER)

    assert run.error is None
    assert len(asked) == 2
    assert asked[1].split(",") == [f for f in asked[0].split(",") if f != STAGE_FIELD]
    stored = session.scalars(
        select(Source).where(Source.clio_type == SourceType.MATTER)
    ).one()
    assert stored.raw_json["matter_stage"] == {"name": "Invented stage"}
