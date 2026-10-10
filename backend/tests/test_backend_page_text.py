"""The firm's source drawer gives each document page its text layer as the image's text
alternative (WCAG 1.1.1, D39); a provider's cited page carries no text (rule 4)."""

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fact, FactKind, Page, User
from tests.fixtures.synthetic_matter import MATTER_ID, ORTHO_ID


def _ok(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


def _ortho_bill(session: Session) -> Fact:
    bill = session.scalars(
        select(Fact).where(
            Fact.kind == FactKind.MEDICAL_BILL,
            Fact.provider_contact_id == ORTHO_ID,
            Fact.page_no.is_not(None),
        )
    ).first()
    assert bill is not None
    return bill


def test_firm_drawer_pages_carry_their_text_layer(
    seeded: Session, client: TestClient
) -> None:
    bill = _ortho_bill(seeded)
    stored = {
        p.page_no: p.text
        for p in seeded.scalars(select(Page).where(Page.source_id == bill.source_id))
    }

    pages = _ok(client.get(f"/api/facts/{bill.id}/source"))["source"]["pages"]

    assert [p["page_no"] for p in pages] == [1, 2]
    text_page, scan = pages
    assert text_page["text"] and text_page["text"] == stored[1]
    assert scan["text"] is None and stored[2] is None  # a scan has no text layer


def test_a_blank_text_layer_is_no_text(seeded: Session, client: TestClient) -> None:
    bill = _ortho_bill(seeded)
    page = seeded.scalars(
        select(Page).where(Page.source_id == bill.source_id, Page.page_no == 1)
    ).one()
    page.text = "  \n"
    seeded.commit()

    pages = _ok(client.get(f"/api/facts/{bill.id}/source"))["source"]["pages"]

    assert pages[0]["text"] is None


def test_the_provider_page_has_no_text(seeded: Session, client: TestClient) -> None:
    user = User(name="Test paralegal", role="paralegal")
    seeded.add(user)
    seeded.commit()
    share = _ok(
        client.post(
            f"/api/matters/{MATTER_ID}/shares",
            json={"provider_contact_id": ORTHO_ID},
            headers={"X-User-Id": str(user.id)},
        ),
        201,
    )
    token = share["url"].rsplit("/p/", 1)[1]
    bill = _ortho_bill(seeded)

    source = _ok(client.get(f"/api/p/{token}/facts/{bill.id}/source"))

    assert source["page"] is not None
    assert set(source["page"]) == {"page_id", "page_no", "image_url"}
