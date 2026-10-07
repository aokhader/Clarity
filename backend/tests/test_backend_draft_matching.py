"""How the draft checker matches figures (D25), one row per case the critic found.

The figures are invented. The internal figure is $123,456.00, a valuation; the link
shows a bills total of $2,480.
"""

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Confidence, Fact, FactKind, Source, SourceType, User
from app.services.draft_check import check_text
from app.services.known_values import KnownValue
from app.services.text_mentions import find_amounts as marked_amounts
from tests.fixtures.synthetic_matter import MATTER_ID, ORTHO_ID

NEVER = "Kept internal: never shared with providers"
INTERNAL_CENTS = 123_456_00
OFFER_DAY = date(2031, 7, 14)
TASK_DAY = date(2031, 8, 4)
INCIDENT_DAY = date(2031, 3, 3)
OTHER_DAY = date(2031, 9, 10)
# Deadlines (D28): only a legal one, by its type, locks its day.
CALENDAR_DAY = date(2031, 10, 6)
EXAM_DAY = date(2031, 10, 8)
UNTYPED_DAY = date(2031, 10, 9)
STATUTE_DAY = date(2033, 1, 17)
ANSWER_DAY = date(2031, 11, 3)


def _fact(fact_id: int, kind: FactKind, value: dict[str, Any] | None = None) -> Fact:
    return Fact(
        id=fact_id,
        kind=kind,
        value_json=value or {},
        source=Source(clio_type=SourceType.NOTE),
        page_no=None,
        confidence=Confidence.HIGH,
    )


SHOWN = [
    KnownValue(
        "the bills total on this link",
        amount_cents=2_480_00,
        facts=(_fact(1, FactKind.MEDICAL_BILL),),
        cues=("total", "bill"),
    )
]
WITHHELD = [
    KnownValue(
        NEVER, amount_cents=INTERNAL_CENTS, facts=(_fact(2, FactKind.CASE_VALUE),)
    ),
    KnownValue(
        NEVER, amount_cents=2_125_000_00, facts=(_fact(3, FactKind.POLICY_LIMIT),)
    ),
    KnownValue(NEVER, on=OFFER_DAY, facts=(_fact(4, FactKind.OFFER),)),
    KnownValue(NEVER, on=TASK_DAY, facts=(_fact(5, FactKind.TASK),)),
    KnownValue(NEVER, on=INCIDENT_DAY, facts=(_fact(6, FactKind.INCIDENT),)),
    KnownValue(NEVER, on=OTHER_DAY, facts=(_fact(7, FactKind.MEDICAL_BILL),)),
    *(
        KnownValue(
            NEVER,
            on=day,
            facts=(_fact(20 + n, FactKind.DEADLINE, {"deadline_type": kind}),),
        )
        for n, (day, kind) in enumerate(
            [
                (CALENDAR_DAY, "calendar_entry"),
                (EXAM_DAY, "examination"),
                (UNTYPED_DAY, None),
                (STATUTE_DAY, "statute_of_limitations"),
                (ANSWER_DAY, "answer due"),
            ]
        )
    ),
    KnownValue(
        "Kept internal: about another provider",
        amount_cents=0,
        facts=(_fact(8, FactKind.MEDICAL_BILL),),
        rank=1,
    ),
]


def _day(on: date) -> str:
    return f"{on:%b} {on.day}, {on.year}"


def _verdict(text: str) -> str:
    return check_text(text, SHOWN, WITHHELD).verdict


# Each way the critic wrote the internal figure; every one must lock.
BYPASSES = [
    ("bare digits", "The figure is 123456 here."),
    ("bare digits with commas", "The figure is 123,456 here."),
    ("bare digits with cents", "The figure is 123456.00 here."),
    ("k", "The figure is 123k here."),
    ("grand", "The figure is 123 grand here."),
    ("dollar sign and grand", "The figure is $123 grand here."),
    ("bucks", "The figure is 123,456 bucks here."),
    (
        "words without dollars",
        "The figure is one hundred twenty-three thousand four hundred fifty-six.",
    ),
    ("trailing USD", "The figure is 123,456 USD here."),
    ("trailing dollar sign", "The figure is 123,456$ here."),
    ("full-width dollar sign", "The figure is ＄123,456 here."),
    ("thin-space thousands", "The figure is $123 456 here."),
    ("dot thousands", "The figure is $123.456 here."),
    ("rounded to $10,000", "The figure is about $120,000."),
    ("rounded to $1,000", "The figure is about $123,000."),
    ("range in words", "It is between $110,000 and $130,000."),
    ("range with a dash", "It is $110k-$130k."),
    ("range with one scale", "It is $110–130k."),
    ("split across sentences", "We hold $100,000 now. Another $23,456 follows."),
    ("three-decimal millions", "The limit is $2.125 million."),
    ("plain-space thousands before dollars", "The figure is 123 456 dollars."),
    ("apostrophe thousands before dollars", "The figure is 123'456 dollars."),
    ("typographic apostrophe before USD", "The figure is 123\u2019456 USD."),
    ("plain-space thousands after a dollar sign", "The figure is $123 456."),
]

# What the critic saw locked that must not be.
NOT_LOCKED = [
    ("$0", "Nothing is owed: $0.", "not_in_file"),
    (
        "a month with an ordinary internal fact in it",
        "We expect to hear back in September 2031.",
        "not_in_file",
    ),
    (
        "a day that only coincides with a task",
        f"Can we talk on {TASK_DAY:%b} {TASK_DAY.day}, {TASK_DAY.year}?",
        "not_in_file",
    ),
    (
        "the incident date",
        f"Since the accident on {INCIDENT_DAY:%B} {INCIDENT_DAY.day}, {INCIDENT_DAY.year}.",
        "not_in_file",
    ),
    (
        "the month of a sensitive day",
        f"Something happened in {OFFER_DAY:%B %Y}.",
        "not_in_file",
    ),
    (
        "a day on a plain calendar entry",
        f"Can you see her on {_day(CALENDAR_DAY)}?",
        "not_in_file",
    ),
    (
        "a day on an exam appointment",
        f"Her exam is on {_day(EXAM_DAY)}.",
        "not_in_file",
    ),
    (
        "a day on a deadline with no type",
        f"Let us speak on {_day(UNTYPED_DAY)}.",
        "not_in_file",
    ),
    ("a year", "We will know more in 2031.", "unchecked"),
    (
        "digits split by a space, with no money marker",
        "We counted 123 456 visits.",
        "unchecked",
    ),
    ("a phone number", "Call 555-0100 with questions.", "unchecked"),
    ("the link's own total", "Your bills total $2,480.", "supported"),
    ("a wrong total of the link's own", "Your bills total $2,500.", "differs"),
]


@pytest.mark.parametrize(("case", "text"), BYPASSES, ids=[c for c, _ in BYPASSES])
def test_every_way_of_writing_an_internal_figure_locks(case: str, text: str) -> None:
    assert _verdict(text) == "do_not_send", case


@pytest.mark.parametrize(
    ("case", "text", "expected"), NOT_LOCKED, ids=[c for c, _, _ in NOT_LOCKED]
)
def test_what_does_not_disclose_is_not_locked(
    case: str, text: str, expected: str
) -> None:
    assert _verdict(text) == expected, case


def test_the_date_of_a_sensitive_fact_locks() -> None:
    text = f"The offer came on {OFFER_DAY:%b} {OFFER_DAY.day}, {OFFER_DAY.year}."

    assert _verdict(text) == "do_not_send"


@pytest.mark.parametrize("day", [STATUTE_DAY, ANSWER_DAY], ids=["statute", "answer"])
def test_the_day_of_a_legal_deadline_locks(day: date) -> None:
    assert _verdict(f"Everything must be ready by {_day(day)}.") == "do_not_send"


@pytest.mark.parametrize(
    "written", ["1 250 dollars", "1'250 dollars", "$1 250", "1\u2019250 USD"]
)
def test_the_call_notes_reader_groups_thousands_beside_a_marker(written: str) -> None:
    # The call-notes check reads amounts through text_mentions (D28: one reader).
    assert [a.cents for a in marked_amounts(written)] == [125_000]


def test_a_lock_cites_the_internal_fact() -> None:
    [sentence] = check_text("The figure is 123 grand.", SHOWN, WITHHELD).sentences

    [mention] = sentence.mentions
    assert (mention.reason, [ref.id for ref in mention.facts]) == (NEVER, [2])


def test_a_range_around_the_links_own_figure_is_not_locked() -> None:
    assert _verdict("Your bills are between $2,000 and $3,000.") != "do_not_send"


# --- Through the share route: computed totals and call notes --------------------------


@pytest.fixture
def share_id(seeded: Session, client: TestClient) -> int:
    user = User(name="Test paralegal", role="paralegal")
    seeded.add(user)
    seeded.commit()
    response = client.post(
        f"/api/matters/{MATTER_ID}/shares",
        json={"provider_contact_id": ORTHO_ID},
        headers={"X-User-Id": str(user.id)},
    )
    return int(response.json()["id"])


def _mention(client: TestClient, share_id: int, text: str) -> dict[str, Any]:
    result = client.post(f"/api/shares/{share_id}/draft-check", json={"text": text})
    [sentence] = result.json()["sentences"]
    [mention] = sentence["mentions"]
    return mention


def test_the_firm_spend_total_locks(
    seeded: Session, client: TestClient, share_id: int
) -> None:
    expenses = list(seeded.scalars(select(Fact).where(Fact.kind == FactKind.EXPENSE)))
    total = sum(f.value_json["amount_cents"] for f in expenses)

    mention = _mention(client, share_id, f"Copies cost the firm ${total // 100:,}.")

    assert mention["verdict"] == "do_not_send"
    assert {ref["id"] for ref in mention["facts"]} == {f.id for f in expenses}


def test_figures_heard_on_a_call_lock(
    seeded: Session, client: TestClient, share_id: int
) -> None:
    note = seeded.scalars(select(Fact).where(Fact.kind == FactKind.CALL_NOTE)).one()
    note.value_json = {**note.value_json, "amounts_cents": [77_700]}
    seeded.commit()

    mention = _mention(client, share_id, "On the call we heard $777.")

    assert mention["verdict"] == "do_not_send"
    assert [ref["id"] for ref in mention["facts"]] == [note.id]


def test_a_zero_the_link_shows_is_supported() -> None:
    zero = KnownValue(
        "a bill on this link", amount_cents=0, facts=(_fact(9, FactKind.MEDICAL_BILL),)
    )

    assert check_text("No charge: $0.", [zero], WITHHELD).verdict == "supported"
