"""The injuries list leads with what the client's treating providers recorded (Pass 1 #14).

A defense exam or an expert review is not attributed to one of the matter's treating
providers, so its findings follow the client's own injuries, however high they score.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Confidence, Fact, FactKind, Origin, Source, SourceType
from app.schemas import validate_payload
from tests.fixtures.synthetic_matter import MATTER_ID, ORTHO_ID


def _exam_finding(session: Session, significance: int) -> Fact:
    source = Source(
        matter_id=MATTER_ID,
        clio_type=SourceType.DOCUMENT,
        clio_id=f"exam-{session.query(Source).count()}",
        raw_json={"name": "Examination report"},
    )
    session.add(source)
    session.flush()
    fact = Fact(
        matter_id=MATTER_ID,
        kind=FactKind.DIAGNOSIS,
        title="Strain resolved on examination",
        value_json=validate_payload(
            FactKind.DIAGNOSIS, {"body_part": "neck", "description": "Resolved"}
        ),
        source_id=source.id,
        page_no=1,
        quote="The strain has resolved.",
        provider_contact_id=None,
        significance=significance,
        confidence=Confidence.HIGH,
        origin=Origin.MODEL,
    )
    session.add(fact)
    session.commit()
    return fact


def test_treating_providers_injuries_come_before_an_exams_findings(
    seeded: Session, client: TestClient
) -> None:
    finding = _exam_finding(seeded, significance=99)

    injuries = client.get(f"/api/matters/{MATTER_ID}/injuries").json()

    providers = [f["provider_contact_id"] for f in injuries]
    assert providers[-1] is None and injuries[-1]["id"] == finding.id
    assert set(providers[:-1]) == {ORTHO_ID}


def test_within_each_group_the_most_significant_comes_first(
    seeded: Session, client: TestClient
) -> None:
    low = _exam_finding(seeded, significance=10)
    high = _exam_finding(seeded, significance=90)

    ids = [f["id"] for f in client.get(f"/api/matters/{MATTER_ID}/injuries").json()]

    assert ids.index(high.id) < ids.index(low.id)
