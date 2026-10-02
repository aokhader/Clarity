"""The brief, injuries, and KPI endpoints that feed the top of the firm view."""

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Digest, DigestKind, Fact, FactKind
from app.services.kpis import kpi_tiles
from tests.fixtures.synthetic_matter import MATTER_ID


def _brief(client: TestClient) -> dict[str, Any]:
    response = client.get(f"/api/matters/{MATTER_ID}/brief")
    assert response.status_code == 200, response.text
    return response.json()


def test_every_brief_sentence_carries_its_sources(
    seeded: Session, client: TestClient
) -> None:
    brief = _brief(client)
    assert brief["headline"] and brief["stage"] == "treating"
    assert brief["stage_facts"]
    assert brief["sentences"]
    assert all(sentence["facts"] for sentence in brief["sentences"])
    assert brief["open_questions"]


def test_a_sentence_citing_an_unknown_fact_is_not_shown(
    seeded: Session, client: TestClient
) -> None:
    shown = len(_brief(client)["sentences"])
    digest = seeded.scalars(select(Digest).where(Digest.kind == DigestKind.BRIEF)).one()
    content = dict(digest.content_json)
    content["sentences"] = [
        *content["sentences"],
        {"text": "An unsourced claim.", "fact_ids": [999_999]},
    ]
    digest.content_json = content
    seeded.commit()

    texts = [s["text"] for s in _brief(client)["sentences"]]
    assert len(texts) == shown and "An unsourced claim." not in texts


def test_no_brief_yet_is_404(seeded: Session, client: TestClient) -> None:
    seeded.execute(delete(Digest).where(Digest.kind == DigestKind.BRIEF))
    seeded.commit()
    assert client.get(f"/api/matters/{MATTER_ID}/brief").status_code == 404


def test_injuries_lists_injuries_and_diagnoses_with_pages(
    seeded: Session, client: TestClient
) -> None:
    response = client.get(f"/api/matters/{MATTER_ID}/injuries")
    assert response.status_code == 200
    injuries = response.json()
    assert {f["kind"] for f in injuries} == {"injury", "diagnosis"}
    assert all(f["page_no"] is not None and f["quote"] for f in injuries)


def test_kpis_with_nothing_in_the_file_are_not_found() -> None:
    tiles = kpi_tiles({kind: [] for kind in FactKind})
    assert [tile.name for tile in tiles] == [
        "case_value",
        "coverage",
        "medical_specials",
        "firm_spend",
    ]
    assert all(tile.values == [] and tile.basis is None for tile in tiles)


def test_header_falls_back_to_the_briefs_stage_marked_inferred(
    seeded: Session, client: TestClient
) -> None:
    # Without a stage in Clio, the brief infers one from other evidence: here, a visit.
    visit = seeded.scalars(
        select(Fact).where(Fact.kind == FactKind.TREATMENT_VISIT)
    ).first()
    assert visit is not None
    digest = seeded.scalars(select(Digest).where(Digest.kind == DigestKind.BRIEF)).one()
    digest.content_json = {**digest.content_json, "stage_fact_ids": [visit.id]}
    seeded.execute(delete(Fact).where(Fact.kind == FactKind.CASE_STAGE))
    seeded.commit()
    stage = client.get(f"/api/matters/{MATTER_ID}").json()["stage"]
    assert stage["stage"] == "treating" and stage["inferred"] is True
    assert stage["facts"]


def test_no_stage_anywhere_shows_none(seeded: Session, client: TestClient) -> None:
    seeded.execute(delete(Fact).where(Fact.kind == FactKind.CASE_STAGE))
    seeded.execute(delete(Digest).where(Digest.kind == DigestKind.BRIEF))
    seeded.commit()
    stage = client.get(f"/api/matters/{MATTER_ID}").json()["stage"]
    assert stage == {"stage": None, "label": None, "inferred": False, "facts": []}
