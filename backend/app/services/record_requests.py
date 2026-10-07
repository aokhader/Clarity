"""Which record requests are still outstanding, read from the dates in the file.

A request fact keeps the status it had when it was written, so a request a provider
answered months later still reads "open". No stored field is needed to close it:

- a dated request is answered by records received from the same provider on or after
  its date;
- an undated request cannot be placed in time, so it counts as answered once the
  provider has sent any dated records;
- what is still open is every ask since the provider last sent records: one
  outstanding request, restated, so it is listed once, as the latest ask.

A request tied to no provider keeps its own status, since nothing in the file can
answer it.
"""

from collections import defaultdict
from datetime import date

from app.models import Fact, FactKind
from app.schemas import RecordRequestPayload


def open_record_requests(facts: list[Fact]) -> list[Fact]:
    """Record requests in `facts` that still read open, before any is matched to records."""
    return [
        f
        for f in facts
        if f.kind is FactKind.RECORD_REQUEST
        and RecordRequestPayload.model_validate(f.value_json).status == "open"
    ]


def outstanding_record_requests(facts: list[Fact]) -> list[Fact]:
    """Open requests the file does not show answered: one per provider, plus the rest.

    `facts` must include the records-received facts that could answer the requests.
    """
    last_received: dict[int, date] = {}
    for fact in facts:
        if (
            fact.kind is FactKind.RECORDS_RECEIVED
            and fact.provider_contact_id is not None
            and fact.event_date is not None
        ):
            pid = fact.provider_contact_id
            last_received[pid] = max(fact.event_date, last_received.get(pid, date.min))
    by_provider: dict[int | None, list[Fact]] = defaultdict(list)
    for request in open_record_requests(facts):
        by_provider[request.provider_contact_id].append(request)
    outstanding = by_provider.pop(None, [])
    for pid, asks in by_provider.items():
        last = last_received.get(pid)
        unanswered = [
            ask
            for ask in asks
            if last is None or (ask.event_date is not None and ask.event_date > last)
        ]
        if unanswered:
            outstanding.append(
                max(
                    unanswered,
                    key=lambda f: (f.event_date or date.min, f.significance, f.id),
                )
            )
    return outstanding
