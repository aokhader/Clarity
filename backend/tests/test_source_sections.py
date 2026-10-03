from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models import Source, SourceType
from app.schemas import SourceSectionOut
from app.services.source_views import source_out


def _sections(
    session: Session, clio_type: SourceType, raw: dict[str, Any]
) -> list[SourceSectionOut]:
    source = Source(matter_id=7, clio_type=clio_type, clio_id="1", raw_json=raw)
    session.add(source)
    session.flush()
    return source_out(session, source).sections


def test_a_matter_reads_as_summary_matter_and_case_fields(session: Session) -> None:
    sections = _sections(
        session,
        SourceType.MATTER,
        {
            "description": "Example v. Example",
            "status": "Open",
            "matter_stage": {"name": "Treating"},
            "open_date": "2024-01-15",
            "custom_field_values": [
                {
                    "field_name": "Estimated value",
                    "field_type": "currency",
                    "value": 1234.5,
                },
                {
                    "field_name": "Date of loss",
                    "field_type": "date",
                    "value": "2024-01-02",
                },
                {
                    "field_name": "Records signed",
                    "field_type": "checkbox",
                    "value": True,
                },
                {
                    "field_name": "Adjuster",
                    "field_type": "text_line",
                    "value": "A. Example",
                },
            ],
        },
    )

    assert [s.heading for s in sections] == ["Summary", "Matter", "Case fields"]
    assert sections[0].text == "Example v. Example"
    matter = {f.label: f for f in sections[1].fields}
    assert (matter["Stage"].value, matter["Opened"].on) == (
        "Treating",
        date(2024, 1, 15),
    )
    value, loss, signed, adjuster = sections[2].fields
    # Money reaches the page as cents and dates as dates, so the page formats both.
    assert (value.amount_cents, value.value) == (123_450, None)
    assert loss.on == date(2024, 1, 2)
    assert (signed.value, adjuster.value) == ("Yes", "A. Example")


def test_a_task_reads_as_its_fields_then_its_description(session: Session) -> None:
    sections = _sections(
        session,
        SourceType.TASK,
        {
            "name": "Request records",
            "description": "Ask the clinic for the full chart.",
            "status": "in_progress",
            "priority": "High",
            "due_at": "2024-02-01T17:00:00Z",
            "assignee": {"name": "Paralegal"},
            "statute_of_limitations": False,
        },
    )

    task, description = sections
    fields = {f.label: f for f in task.fields}
    assert fields["Status"].value == "In progress"
    assert fields["Due"].on == date(2024, 2, 1)
    assert fields["Assigned to"].value == "Paralegal"
    # Empty and false values are left out rather than shown as blanks.
    assert "Completed" not in fields and "Statute of limitations" not in fields
    assert (description.heading, description.text) == (
        "Description",
        "Ask the clinic for the full chart.",
    )


def test_other_sources_keep_their_plain_text(session: Session) -> None:
    assert (
        _sections(
            session,
            SourceType.NOTE,
            {"subject": "Call", "detail": "Spoke with the client."},
        )
        == []
    )
