"""Calls (docs/calls-contract.md): who to call, consent, transcript, notes in the background.

The notes extractor is pipeline's and calls a model, so these tests swap in an invented
one. Nothing here dials a number.
"""

import time
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.digest.llm import ModelsNotConfigured
from app.models import Source, SourceType
from app.services import call_notes, calls
from tests.fixtures.synthetic_matter import INSURER_ID, MATTER_ID, ORTHO_ID, THERAPY_ID

CONSENT = "This call is transcribed by the browser's speech service. Agreed."
TRANSCRIPT = "Hello. We will send the itemized bill by Monday. It comes to $1,250."
QUOTE = "We will send the itemized bill by Monday"
POLL_S = 10.0


@dataclass
class _Draft:
    kind: str
    text: str
    quote: str
    quote_start: int
    quote_end: int
    amounts_cents: list[int] = field(default_factory=list)
    dates: list[dict[str, Any]] = field(default_factory=list)


def _note(quote: str = QUOTE, start: int | None = None) -> _Draft:
    begin = TRANSCRIPT.index(quote) if start is None else start
    return _Draft(
        "commitment", "Provider will send the bill", quote, begin, begin + len(quote)
    )


@pytest.fixture
def models_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        calls, "get_settings", lambda: SimpleNamespace(models_configured=True)
    )


def _use_extractor(
    monkeypatch: pytest.MonkeyPatch, notes: list[_Draft] | Exception
) -> None:
    def extract(session: Session, transcript: str, **context: Any) -> SimpleNamespace:
        assert transcript == TRANSCRIPT and context["matter_id"] == MATTER_ID
        if isinstance(notes, Exception):
            raise notes
        return SimpleNamespace(notes=notes, dropped=[])

    monkeypatch.setattr(call_notes, "_extractor", lambda: extract)


def _targets(client: TestClient) -> dict[str, dict[str, Any]]:
    response = client.get(f"/api/matters/{MATTER_ID}/calls/next")
    assert response.status_code == 200, response.text
    return {t["target_id"]: t for t in response.json()}


def _start(
    client: TestClient, target_id: str = f"contact:{ORTHO_ID}", **body: Any
) -> Any:
    return client.post(
        f"/api/matters/{MATTER_ID}/calls",
        json={
            "target_id": target_id,
            "consent_confirmed": True,
            "consent_text": CONSENT,
        }
        | body,
    )


def _ended_call(client: TestClient) -> dict[str, Any]:
    call = _start(client).json()
    client.put(
        f"/api/calls/{call['call_id']}/transcript",
        json={"text": TRANSCRIPT, "final": True},
    )
    ended = client.post(f"/api/calls/{call['call_id']}/end")
    assert ended.status_code == 200, ended.text
    return _settled(client, call["call_id"])


def _settled(client: TestClient, call_id: int) -> dict[str, Any]:
    deadline = time.monotonic() + POLL_S
    while time.monotonic() < deadline:
        detail = client.get(f"/api/calls/{call_id}").json()
        if detail["call"]["notes_status"] != "running":
            return detail
        time.sleep(0.05)
    raise AssertionError("the notes were still running")


def test_who_to_call_lists_each_contact_an_open_item_waits_on(
    seeded: Session, client: TestClient
) -> None:
    targets = _targets(client)

    ortho = targets[f"contact:{ORTHO_ID}"]
    assert ortho["role"] == "provider" and ortho["reason"] and ortho["reason_fact"]
    assert targets[f"contact:{INSURER_ID}"]["role"] == "insurer"
    # The synthetic contacts have no number in Clio, and that is said, not guessed.
    assert ortho["phone"] is None and ortho["phone_source"] is None
    assert f"contact:{THERAPY_ID}" not in targets  # nothing waits on it


def test_a_number_synced_from_clio_is_offered(
    seeded: Session, client: TestClient
) -> None:
    contact = seeded.scalars(
        select(Source).where(
            Source.clio_type == SourceType.CONTACT, Source.clio_id == str(ORTHO_ID)
        )
    ).one()
    contact.raw_json = contact.raw_json | {
        "phone_numbers": [{"number": "555-0100", "name": "Work"}]
    }
    seeded.commit()

    ortho = _targets(client)[f"contact:{ORTHO_ID}"]

    assert (ortho["phone"], ortho["phone_source"]) == ("555-0100", "clio")


def test_last_contact_cites_the_latest_communication(
    seeded: Session, client: TestClient
) -> None:
    target = client.post(
        f"/api/matters/{MATTER_ID}/calls",
        json={
            "target_id": f"contact:{THERAPY_ID}",
            "consent_confirmed": True,
            "consent_text": CONSENT,
        },
    ).json()["target"]

    # The synthetic therapy office emailed 20 days ago.
    assert target["last_contact_days"] == 20
    assert target["last_contact_fact"]["source_type"] == "communication"


def test_a_typed_number_is_stored_in_clarity_and_listed(
    seeded: Session, client: TestClient
) -> None:
    response = client.post(
        f"/api/matters/{MATTER_ID}/call-numbers",
        json={"name": "Test line", "phone": "555-0199"},
    )

    assert response.status_code == 201, response.text
    typed = response.json()
    assert typed["target_id"].startswith("entered:")
    assert (typed["phone"], typed["phone_source"], typed["role"]) == (
        "555-0199",
        "entered",
        "other",
    )
    assert typed["last_contact_days"] is None and typed["last_contact_fact"] is None
    assert typed["target_id"] in _targets(client)


def test_a_call_needs_consent_and_a_known_target(
    seeded: Session, client: TestClient
) -> None:
    assert _start(client, consent_confirmed=False).status_code == 422
    assert _start(client, "contact:999999").status_code == 404
    assert _start(client, "entered:999999").status_code == 404

    started = _start(client)

    assert started.status_code == 201, started.text
    call = started.json()
    assert call["consent_text"] == CONSENT
    assert call["notes_status"] == "not_started" and call["ended_at"] is None
    assert call["target"]["target_id"] == f"contact:{ORTHO_ID}"


def test_the_transcript_is_saved_and_read_back(
    seeded: Session, client: TestClient
) -> None:
    call_id = _start(client).json()["call_id"]

    client.put(
        f"/api/calls/{call_id}/transcript", json={"text": "Hello.", "final": False}
    )
    client.put(
        f"/api/calls/{call_id}/transcript", json={"text": TRANSCRIPT, "final": True}
    )

    detail = client.get(f"/api/calls/{call_id}").json()
    assert detail["transcript"] == TRANSCRIPT and detail["notes"] == []
    assert [
        c["call_id"] for c in client.get(f"/api/matters/{MATTER_ID}/calls").json()
    ] == [call_id]


def test_without_model_settings_the_transcript_stands_alone(
    seeded: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        calls, "get_settings", lambda: SimpleNamespace(models_configured=False)
    )

    detail = _ended_call(client)

    assert detail["call"]["notes_status"] == "no_model"
    assert detail["call"]["ended_at"] is not None
    assert detail["transcript"] == TRANSCRIPT and detail["notes"] == []


def test_notes_cite_the_transcript_and_open_it_in_the_drawer(
    seeded: Session,
    client: TestClient,
    models_on: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_extractor(monkeypatch, [_note(), _note("not in the transcript", start=0)])

    detail = _ended_call(client)

    assert detail["call"]["notes_status"] == "done"
    [note] = detail["notes"]  # the note whose span does not hold its quote is dropped
    assert note["kind"] == "commitment"
    assert TRANSCRIPT[note["quote_start"] : note["quote_end"]] == QUOTE
    source = client.get(f"/api/facts/{note['fact']['id']}/source").json()
    assert (
        source["fact"]["quote"] == QUOTE and source["fact"]["visibility"] == "internal"
    )
    assert source["source"]["source_type"] == "call"
    assert source["source"]["text"] == TRANSCRIPT


def test_a_call_with_notes_becomes_the_latest_contact(
    seeded: Session,
    client: TestClient,
    models_on: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_extractor(monkeypatch, [_note()])
    note = _ended_call(client)["notes"][0]

    ortho = _targets(client)[f"contact:{ORTHO_ID}"]

    assert ortho["last_contact_days"] == 0
    assert ortho["last_contact_fact"]["id"] == note["fact"]["id"]


def test_failed_notes_say_so_and_ending_again_retries(
    seeded: Session,
    client: TestClient,
    models_on: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_extractor(monkeypatch, RuntimeError("the model returned nothing usable"))
    detail = _ended_call(client)
    assert detail["call"]["notes_status"] == "failed"

    _use_extractor(monkeypatch, [_note()])
    client.post(f"/api/calls/{detail['call']['call_id']}/end")

    retried = _settled(client, detail["call"]["call_id"])
    assert retried["call"]["notes_status"] == "done" and len(retried["notes"]) == 1


def test_missing_models_inside_the_job_report_no_model(
    seeded: Session,
    client: TestClient,
    models_on: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_extractor(monkeypatch, ModelsNotConfigured("no model set"))

    assert _ended_call(client)["call"]["notes_status"] == "no_model"


def test_the_transcript_is_closed_once_notes_exist(
    seeded: Session,
    client: TestClient,
    models_on: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_extractor(monkeypatch, [_note()])
    call_id = _ended_call(client)["call"]["call_id"]

    response = client.put(
        f"/api/calls/{call_id}/transcript", json={"text": "x", "final": True}
    )

    assert response.status_code == 409
    assert client.get("/api/calls/999999").status_code == 404
