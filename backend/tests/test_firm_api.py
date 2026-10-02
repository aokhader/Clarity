"""Firm-view endpoints, exercised over HTTP against the synthetic matter."""

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Confidence, Fact, FactKind, Origin, Page, Source, SourceType
from tests.fixtures.synthetic_matter import MATTER_ID


def _get(client: TestClient, path: str) -> Any:
    response = client.get(path)
    assert response.status_code == 200, response.text
    return response.json()


def _kpi(header: dict[str, Any], name: str) -> dict[str, Any]:
    return next(k for k in header["kpis"] if k["name"] == name)


def test_lists_the_synced_matter(seeded: Session, client: TestClient) -> None:
    matters = _get(client, "/api/matters")
    assert [m["matter_id"] for m in matters] == [MATTER_ID]


def test_unknown_matter_is_404(seeded: Session, client: TestClient) -> None:
    assert client.get("/api/matters/999").status_code == 404
    assert client.get("/api/matters/999/feed").status_code == 404


def test_header_carries_stage_dates_and_sourced_kpis(
    seeded: Session, client: TestClient
) -> None:
    header = _get(client, f"/api/matters/{MATTER_ID}")
    assert header["stage"]["stage"] == "treating"
    assert header["stage"]["facts"]
    assert header["incident"] and header["last_client_contact"]
    assert header["digested"] and header["last_sync"]

    case_value = _kpi(header, "case_value")["values"]
    assert [(v["low_cents"], v["high_cents"]) for v in case_value] == [
        (7_500_000, 15_000_000)
    ]
    # Two sources name different limits, so the tile shows both.
    coverage = _kpi(header, "coverage")["values"]
    assert sorted(v["amount_cents"] for v in coverage) == [5_000_000, 10_000_000]
    # The specials field agrees with the sum of the bills: one value, three sources.
    specials = _kpi(header, "medical_specials")
    assert [v["amount_cents"] for v in specials["values"]] == [344_000]
    assert len(specials["values"][0]["facts"]) == 3
    assert specials["basis"] == "Matches the sum of 2 bills"
    spend = _kpi(header, "firm_spend")
    assert [v["amount_cents"] for v in spend["values"]] == [6_000]


def test_action_board_groups_do_not_overlap(
    seeded: Session, client: TestClient
) -> None:
    actions = _get(client, f"/api/matters/{MATTER_ID}/actions")
    titles = {group: [f["title"] for f in facts] for group, facts in actions.items()}
    assert titles["overdue"] == ["Request updated orthopedic records"]
    # The record request comes from the overdue task, so it is not listed again.
    assert titles["waiting_on_others"] == ["Confirm policy limits with adjuster"]
    assert titles["upcoming"] == [
        "Client check-in call",
        "Draft demand letter",
        "Statute of limitations",
    ]


def test_feed_is_ordered_by_significance(seeded: Session, client: TestClient) -> None:
    feed = _get(client, f"/api/matters/{MATTER_ID}/feed?limit=5")
    scores = [f["significance"] for f in feed]
    assert len(feed) == 5 and scores == sorted(scores, reverse=True)
    assert feed[0]["kind"] == "offer"


def test_timeline_filters_by_kind_and_text(seeded: Session, client: TestClient) -> None:
    bills = _get(client, f"/api/matters/{MATTER_ID}/timeline?kind=medical_bill")
    assert {f["kind"] for f in bills} == {"medical_bill"} and len(bills) == 2
    liens = _get(client, f"/api/matters/{MATTER_ID}/timeline?q=LIEN")
    assert {f["kind"] for f in liens} == {"lien"}


def test_document_source_lists_pages_and_serves_images(
    seeded: Session, client: TestClient
) -> None:
    bill = seeded.scalars(
        select(Fact).where(Fact.kind == FactKind.LIEN, Fact.matter_id == MATTER_ID)
    ).one()
    source = _get(client, f"/api/facts/{bill.id}/source")
    assert source["fact"]["page_no"] == 2
    pages = source["source"]["pages"]
    assert [p["page_no"] for p in pages] == [1, 2]
    image = client.get(pages[1]["image_url"])
    assert image.status_code == 200 and image.content.startswith(b"\x89PNG")


def test_note_source_text_contains_the_quote(
    seeded: Session, client: TestClient
) -> None:
    fact = seeded.scalars(
        select(Fact).where(Fact.kind == FactKind.LIABILITY, Fact.matter_id == MATTER_ID)
    ).one()
    source = _get(client, f"/api/facts/{fact.id}/source")["source"]
    assert source["source_type"] == "note"
    assert fact.quote and fact.quote in source["text"]


def test_document_fact_without_a_page_is_never_shown(
    seeded: Session, client: TestClient
) -> None:
    document = seeded.scalars(
        select(Source).where(Source.clio_type == SourceType.DOCUMENT)
    ).one()
    unsourced = Fact(
        matter_id=MATTER_ID,
        kind=FactKind.OTHER,
        title="Claim with no page",
        value_json={"alt_values": [], "corroborating_source_ids": [], "detail": None},
        source_id=document.id,
        significance=100,
        confidence=Confidence.HIGH,
        origin=Origin.MODEL,
    )
    seeded.add(unsourced)
    seeded.commit()
    feed = _get(client, f"/api/matters/{MATTER_ID}/feed?limit=50")
    assert unsourced.id not in {f["id"] for f in feed}
    assert client.get(f"/api/facts/{unsourced.id}/source").status_code == 404


def test_page_image_outside_the_data_dir_is_refused(
    seeded: Session, client: TestClient
) -> None:
    page = seeded.scalars(select(Page)).first()
    assert page is not None
    page.image_path = "../../outside.png"
    seeded.commit()
    assert client.get(f"/api/pages/{page.id}/image").status_code == 404
