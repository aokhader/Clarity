"""The draft checker: amounts and dates in text meant for a provider, checked in code.

The synthetic matter's first provider has one bill and one lien for the same charges,
so its link shows a bills total and a larger sum of the items listed under bills.
"""

import json
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fact, FactKind, User
from app.services.draft_check import check_text
from app.services.known_values import KnownValue
from app.services.text_mentions import (
    DatePrecision,
    find_amounts,
    find_dates,
    sentence_spans,
)
from tests.fixtures.synthetic_matter import INSURER_ID, MATTER_ID, ORTHO_ID, THERAPY_ID

# --- Parsing ------------------------------------------------------------------------


def test_only_numbers_marked_as_money_are_amounts() -> None:
    text = (
        "Paid $2,480.50, about $12k, USD 1,200, 1,200 dollars and twelve thousand "
        "five hundred dollars. Call 555-1234 about 3 visits in 2031."
    )
    assert [a.cents for a in find_amounts(text)] == [
        248_050,
        1_200_000,
        120_000,
        120_000,
        1_250_000,
    ]


def test_an_amount_is_compared_at_the_precision_it_was_written() -> None:
    to_the_cent, to_the_dollar, to_the_thousand = find_amounts("$2,480.50 $2,480 $12k")
    assert to_the_cent.matches(248_050) and not to_the_cent.matches(248_051)
    assert to_the_dollar.matches(248_049) and not to_the_dollar.matches(248_100)
    assert to_the_thousand.matches(1_249_900) and not to_the_thousand.matches(1_260_000)


def test_dates_are_read_in_every_written_form() -> None:
    text = (
        "Jul. 14, 2031; 14 July 2031; 7/14/31; 2031-07-14; July 2031; Sept 6; "
        "Feb 30, 2031; Policy 2031"
    )
    found = [(d.on, d.precision) for d in find_dates(text)]
    day = (date(2031, 7, 14), DatePrecision.DAY)
    assert found == [
        day,
        day,
        day,
        day,
        (date(2031, 7, 1), DatePrecision.MONTH),
        (date(2000, 9, 6), DatePrecision.MONTH_DAY),
    ]


def test_sentences_split_at_their_ends_only() -> None:
    text = "Paid $1,234.56 on Jul. 14, 2031. Dr. Lee agreed!\n- Next item"
    assert [text[s:e] for s, e in sentence_spans(text)] == [
        "Paid $1,234.56 on Jul. 14, 2031.",
        "Dr. Lee agreed!",
        "- Next item",
    ]


def test_the_matcher_works_without_a_share() -> None:
    fee = KnownValue("the fee", amount_cents=100_00, cues=("fee",))
    secret = KnownValue("Kept internal", amount_cents=500_00)

    result = check_text("The fee is $100. The fee is $120. Pay $500.", [fee], [secret])

    assert [s.verdict for s in result.sentences] == [
        "supported",
        "differs",
        "do_not_send",
    ]
    assert result.sentences[1].mentions[0].file_amount_cents == 100_00


# --- Over HTTP, against the synthetic matter -----------------------------------------


@pytest.fixture
def user_id(seeded: Session) -> int:
    user = User(name="Test paralegal", role="paralegal")
    seeded.add(user)
    seeded.commit()
    return user.id


def _fact(session: Session, kind: FactKind, provider: int | None) -> Fact:
    fact = session.scalars(
        select(Fact).where(Fact.kind == kind, Fact.provider_contact_id == provider)
    ).first()
    assert fact is not None
    return fact


def _share(client: TestClient, user_id: int, **body: Any) -> int:
    response = client.post(
        f"/api/matters/{MATTER_ID}/shares",
        json={"provider_contact_id": ORTHO_ID} | body,
        headers={"X-User-Id": str(user_id)},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def _check(client: TestClient, share_id: int, text: str) -> dict[str, Any]:
    response = client.post(f"/api/shares/{share_id}/draft-check", json={"text": text})
    assert response.status_code == 200, response.text
    return response.json()


def _only_mention(result: dict[str, Any]) -> dict[str, Any]:
    [sentence] = result["sentences"]
    [mention] = sentence["mentions"]
    return mention


def _written(day: date) -> str:
    """A date the way the app's generated update writes it: Jul 14, 2031."""
    return f"{day:%b} {day.day}, {day.year}"


def test_the_generated_update_is_supported_lien_included(
    client: TestClient, seeded: Session, user_id: int
) -> None:
    bill = _fact(seeded, FactKind.MEDICAL_BILL, ORTHO_ID)
    assert bill.event_date is not None
    text = (
        "Your bills on file: 2 bills, $4,960 in total\n"
        f"- {_written(bill.event_date)}: {bill.title}\n"
    )

    result = _check(client, _share(client, user_id), text)

    assert result["verdict"] == "supported"
    cited = {
        ref["id"]
        for s in result["sentences"]
        for m in s["mentions"]
        for ref in m["facts"]
    }
    assert bill.id in cited


def test_a_wrong_bills_total_differs_and_offers_the_files_value(
    client: TestClient, seeded: Session, user_id: int
) -> None:
    bill = _fact(seeded, FactKind.MEDICAL_BILL, ORTHO_ID)

    mention = _only_mention(
        _check(client, _share(client, user_id), "The total of your bills is $2,500.")
    )

    assert mention["verdict"] == "differs"
    assert mention["file_amount_cents"] == bill.value_json["amount_cents"]
    assert [ref["id"] for ref in mention["facts"]] == [bill.id]


def test_an_amount_nothing_in_the_file_states_is_not_in_file(
    client: TestClient, user_id: int
) -> None:
    mention = _only_mention(
        _check(client, _share(client, user_id), "We expect about $12k more.")
    )

    assert mention["verdict"] == "not_in_file"
    assert mention["facts"] == []


def test_an_internal_amount_is_do_not_send_and_reveals_nothing(
    client: TestClient, seeded: Session, user_id: int
) -> None:
    offer = _fact(seeded, FactKind.OFFER, None)
    text = f"The insurer offered ${offer.value_json['amount_cents'] // 100:,}."

    result = _check(client, _share(client, user_id), text)
    mention = _only_mention(result)

    assert result["verdict"] == "do_not_send"
    assert mention["reason"] == "Kept internal: never shared with providers"
    assert mention["facts"] == []
    assert mention["file_amount_cents"] is None and mention["file_date"] is None
    sent_back = json.dumps(result)
    assert offer.title not in sent_back
    assert offer.quote is not None and offer.quote not in sent_back


def test_another_providers_bill_is_do_not_send(
    client: TestClient, seeded: Session, user_id: int
) -> None:
    other = _fact(seeded, FactKind.MEDICAL_BILL, THERAPY_ID)
    text = f"Therapy charges came to ${other.value_json['amount_cents'] // 100:,}."

    mention = _only_mention(_check(client, _share(client, user_id), text))

    assert mention["verdict"] == "do_not_send"
    assert mention["reason"] == "Kept internal: about another provider"


def test_a_bill_the_firm_hid_is_do_not_send(
    client: TestClient, seeded: Session, user_id: int
) -> None:
    bill = _fact(seeded, FactKind.MEDICAL_BILL, ORTHO_ID)
    lien = _fact(seeded, FactKind.LIEN, ORTHO_ID)
    share_id = _share(client, user_id, hidden_fact_ids=[bill.id, lien.id])

    mention = _only_mention(_check(client, share_id, "Your bill was $2,480."))

    assert mention["verdict"] == "do_not_send"
    assert mention["reason"] == "Hidden from this link by the firm"


def test_a_limit_is_do_not_send_until_the_link_shares_limits(
    client: TestClient, user_id: int
) -> None:
    def check(settings: dict[str, bool]) -> dict[str, Any]:
        response = client.post(
            f"/api/matters/{MATTER_ID}/shares/draft-check",
            json={
                "share": {"provider_contact_id": ORTHO_ID, "settings": settings},
                "text": "The per-person policy limit is $50,000.",
            },
        )
        assert response.status_code == 200, response.text
        return _only_mention(response.json())

    withheld = check({})
    assert withheld["verdict"] == "do_not_send"
    assert withheld["reason"] == "This link does not share policy limits"
    assert check({"coverage_limits": True})["verdict"] == "supported"


def test_the_share_note_does_not_vouch_for_itself(
    client: TestClient, user_id: int
) -> None:
    share_id = _share(client, user_id, note="We agreed to $12,345.")

    assert (
        _only_mention(_check(client, share_id, "We agreed to $12,345."))["verdict"]
        == "not_in_file"
    )


def test_a_sentence_takes_its_worst_verdict(client: TestClient, user_id: int) -> None:
    result = _check(
        client,
        _share(client, user_id),
        "Your bills total $2,480 but the demand was $150,000. Thank you for your help.",
    )

    assert [s["verdict"] for s in result["sentences"]] == ["do_not_send", "unchecked"]
    assert [m["verdict"] for m in result["sentences"][0]["mentions"]] == [
        "supported",
        "do_not_send",
    ]
    assert result["verdict"] == "do_not_send"


def test_dates_match_at_their_written_precision_and_a_wrong_one_differs(
    client: TestClient, seeded: Session, user_id: int
) -> None:
    share_id = _share(client, user_id)
    expires_on = date.fromisoformat(
        client.get(f"/api/shares/{share_id}/preview").json()["payload"]["expires_on"]
    )
    records = _fact(seeded, FactKind.RECORDS_RECEIVED, ORTHO_ID)
    assert records.event_date is not None
    day = records.event_date
    numeric = f"{day.month}/{day.day}/{day:%y}"
    no_year = f"{day:%B} {day.day}"
    # Years past every date in the synthetic matter, so it can only differ.
    wrong = date(expires_on.year + 5, expires_on.month, 1)

    result = _check(
        client,
        share_id,
        f"Records came {numeric}. Again on {no_year}. "
        f"The link stops working after {_written(wrong)}.",
    )

    verdicts = [s["mentions"][0]["verdict"] for s in result["sentences"]]
    assert verdicts == ["supported", "supported", "differs"]
    assert result["sentences"][2]["mentions"][0]["file_date"] == expires_on.isoformat()


def test_offsets_count_javascript_string_units(
    client: TestClient, user_id: int
) -> None:
    text = "\U0001f642 Your bills total $2,480."

    mention = _only_mention(_check(client, _share(client, user_id), text))

    # The emoji is one Python character and two UTF-16 units.
    assert mention["start"] == text.index("$") + 1
    assert mention["text"] == "$2,480"


def test_a_revoked_link_cannot_be_checked(client: TestClient, user_id: int) -> None:
    share_id = _share(client, user_id)
    client.post(f"/api/shares/{share_id}/revoke")

    response = client.post(f"/api/shares/{share_id}/draft-check", json={"text": "$1"})

    assert response.status_code == 410


def test_only_a_medical_provider_can_be_checked_for(
    client: TestClient, seeded: Session
) -> None:
    response = client.post(
        f"/api/matters/{MATTER_ID}/shares/draft-check",
        json={"share": {"provider_contact_id": INSURER_ID}, "text": "$1"},
    )

    assert response.status_code == 422
