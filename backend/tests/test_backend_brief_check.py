"""The brief is checked against today's file when it is served (D12, D14).

The synthetic matter's brief is rewritten in each test to state one thing, then read
back through the API: the stored text never changes, only the verdict on it.
"""

from datetime import date, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Digest, DigestKind, Fact, FactKind
from app.services.bills import billed_total_cents
from tests.fixtures.synthetic_matter import MATTER_ID, ORTHO_ID, THERAPY_ID


def _fact(session: Session, kind: FactKind, provider: int | None = None) -> Fact:
    fact = session.scalars(
        select(Fact).where(Fact.kind == kind, Fact.provider_contact_id == provider)
    ).first()
    assert fact is not None
    return fact


def _store(session: Session, **content: Any) -> None:
    digest = session.scalars(
        select(Digest).where(Digest.kind == DigestKind.BRIEF)
    ).one()
    digest.content_json = dict(digest.content_json) | content
    session.commit()


def _brief(client: TestClient) -> dict[str, Any]:
    response = client.get(f"/api/matters/{MATTER_ID}/brief")
    assert response.status_code == 200, response.text
    return response.json()


def _one_sentence(
    session: Session, client: TestClient, text: str, cited: list[Fact]
) -> dict[str, Any]:
    _store(session, sentences=[{"text": text, "fact_ids": [f.id for f in cited]}])
    [sentence] = _brief(client)["sentences"]
    return sentence


def _written(day: date) -> str:
    return f"{day:%b} {day.day}, {day.year}"


def _ids(mention: dict[str, Any]) -> set[int]:
    return {ref["id"] for ref in mention["facts"]}


def test_the_seeded_brief_agrees_with_the_file(
    seeded: Session, client: TestClient
) -> None:
    brief = _brief(client)

    assert {s["verdict"] for s in brief["sentences"]} <= {"supported", "unchecked"}
    assert brief["headline_facts"] == []  # stored before D14
    priced = [s for s in brief["sentences"] if s["mentions"]]
    assert priced and all(m["facts"] for s in priced for m in s["mentions"])


def test_a_stale_bills_total_differs_with_todays_total_and_its_bills(
    seeded: Session, client: TestClient
) -> None:
    bills = [
        _fact(seeded, FactKind.MEDICAL_BILL, ORTHO_ID),
        _fact(seeded, FactKind.MEDICAL_BILL, THERAPY_ID),
    ]
    specials = _fact(seeded, FactKind.MEDICAL_SPECIALS)

    sentence = _one_sentence(
        seeded, client, "Medical bills total $9,999 so far.", [specials]
    )

    [mention] = sentence["mentions"]
    assert sentence["verdict"] == mention["verdict"] == "differs"
    assert mention["file_amount_cents"] == billed_total_cents(bills)
    assert {b.id for b in bills} <= _ids(mention)


def test_a_figure_its_own_citation_states_cites_only_that_fact(
    seeded: Session, client: TestClient
) -> None:
    offer = _fact(seeded, FactKind.OFFER)
    cents = offer.value_json["amount_cents"]

    sentence = _one_sentence(
        seeded, client, f"The insurer offered ${cents // 100:,}.", [offer]
    )

    [mention] = sentence["mentions"]
    assert mention["verdict"] == "supported"
    assert _ids(mention) == {offer.id}


def test_a_figure_in_its_own_clause_is_not_tied_to_another_clauses_subject(
    seeded: Session, client: TestClient
) -> None:
    specials = _fact(seeded, FactKind.MEDICAL_SPECIALS)
    cents = specials.value_json["amount_cents"]

    sentence = _one_sentence(
        seeded,
        client,
        f"Medical bills total ${cents // 100:,} and lost wages come to $7,777.",
        [specials],
    )

    assert [m["verdict"] for m in sentence["mentions"]] == [
        "supported",
        "not_in_file",
    ]


def test_one_date_over_two_records_dated_apart_differs(
    seeded: Session, client: TestClient
) -> None:
    ortho = _fact(seeded, FactKind.TREATMENT_VISIT, ORTHO_ID)
    therapy = _fact(seeded, FactKind.TREATMENT_VISIT, THERAPY_ID)
    assert ortho.event_date and therapy.event_date
    assert ortho.event_date != therapy.event_date

    sentence = _one_sentence(
        seeded,
        client,
        f"An exam on {_written(ortho.event_date)} found the client improving.",
        [ortho, therapy],
    )

    [mention] = sentence["mentions"]
    assert mention["verdict"] == "differs"
    assert mention["file_date"] == therapy.event_date.isoformat()
    assert _ids(mention) == {therapy.id}


def test_a_date_no_fact_carries_is_set_against_the_nearest_cited_date(
    seeded: Session, client: TestClient
) -> None:
    ortho = _fact(seeded, FactKind.TREATMENT_VISIT, ORTHO_ID)
    therapy = _fact(seeded, FactKind.TREATMENT_VISIT, THERAPY_ID)
    assert ortho.event_date and therapy.event_date
    unknown = therapy.event_date + timedelta(days=1)

    sentence = _one_sentence(
        seeded,
        client,
        f"Visits on {_written(ortho.event_date)} and {_written(unknown)}.",
        [ortho, therapy],
    )

    first, second = sentence["mentions"]
    assert first["verdict"] == "supported" and _ids(first) == {ortho.id}
    assert second["verdict"] == "differs"
    assert second["file_date"] == therapy.event_date.isoformat()


def test_the_headline_cites_its_stored_facts_and_is_checked(
    seeded: Session, client: TestClient
) -> None:
    offer = _fact(seeded, FactKind.OFFER)
    cents = offer.value_json["amount_cents"]
    _store(
        seeded,
        headline=f"The insurer offered ${cents // 100:,}.",
        headline_fact_ids=[offer.id, 999_999],
    )

    brief = _brief(client)

    # An id that cannot be shown is dropped, as in a sentence.
    assert [ref["id"] for ref in brief["headline_facts"]] == [offer.id]
    assert brief["headline_verdict"] == "supported"
    assert _ids(brief["headline_mentions"][0]) == {offer.id}


# --- A cited record's own date (D53) -----------------------------------------------------

# A day no fact or record of the synthetic matter carries.
_RECORD_DAY = date(2019, 3, 4)


def _redate(session: Session, fact: Fact, key: str = "date") -> None:
    """Give the fact's record `_RECORD_DAY` as its own date."""
    fact.source.raw_json = {**fact.source.raw_json, key: _RECORD_DAY.isoformat()}


def test_a_date_its_cited_notes_own_record_gives_is_supported(
    seeded: Session, client: TestClient
) -> None:
    damages = _fact(seeded, FactKind.ECONOMIC_DAMAGES)  # read from a note
    damages.event_date = None  # so only the note's own date can support the day
    _redate(seeded, damages)

    sentence = _one_sentence(
        seeded,
        client,
        f"The intake note of {_written(_RECORD_DAY)} puts damages at $8,440.",
        [damages],
    )

    on_day, amount = sentence["mentions"]
    assert sentence["verdict"] == "supported"
    assert on_day["verdict"] == amount["verdict"] == "supported"
    assert _ids(on_day) == {damages.id}


def test_another_notes_date_is_not_supported_by_a_note_it_does_not_cite(
    seeded: Session, client: TestClient
) -> None:
    damages = _fact(seeded, FactKind.ECONOMIC_DAMAGES)
    damages.event_date = None
    filed = _fact(seeded, FactKind.LITIGATION_EVENT)  # another note, not cited
    assert filed.source_id != damages.source_id
    _redate(seeded, filed)

    sentence = _one_sentence(
        seeded,
        client,
        f"On {_written(_RECORD_DAY)} the note put damages at $8,440.",
        [damages],
    )

    on_day, _amount = sentence["mentions"]
    assert on_day["verdict"] == "not_in_file"


def test_a_record_dated_the_day_a_sentence_gives_is_not_dated_otherwise(
    seeded: Session, client: TestClient
) -> None:
    # The note tells of an event on another day; the sentence gives the note's own date.
    liability = _fact(seeded, FactKind.LIABILITY)
    assert liability.event_date is not None and liability.event_date != _RECORD_DAY
    _redate(seeded, liability)

    sentence = _one_sentence(
        seeded,
        client,
        f"A note of {_written(_RECORD_DAY)} says the report faults the other driver.",
        [liability],
    )

    [on_day] = sentence["mentions"]
    assert on_day["verdict"] == "supported"
    assert _ids(on_day) == {liability.id}


def test_a_documents_own_date_counts_for_the_fact_read_from_it(
    seeded: Session, client: TestClient
) -> None:
    injury = _fact(seeded, FactKind.INJURY, ORTHO_ID)  # read from a document page
    _redate(seeded, injury, key="received_at")

    sentence = _one_sentence(
        seeded,
        client,
        f"A report dated {_written(_RECORD_DAY)} finds a neck strain.",
        [injury],
    )

    [on_day] = sentence["mentions"]
    assert on_day["verdict"] == "supported"
