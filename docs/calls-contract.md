# Calls: API contract (D8, D15, D22)

Written by the lead before any Calls code, so the UI and the server can be built at the same time. Backend implements it in `schemas.py` and `types.ts` (C-B). Field names are binding; a change goes through the lead. Read `docs/briefs/calls.md` for the browser and consent rules behind it.

## Rules it encodes

- **Clio stays read-only.** Calls, transcripts, typed numbers and notes live only in Clarity's database, in new tables, so nothing needs `cli reset`.
- **Consent first.** The server refuses to start a call unless `consent_confirmed` is true, and it stores the consent wording that was shown.
- **Notes are sourced.** Every note carries a span of its call's transcript, which code checks. A note whose span does not contain its text is dropped.
- **Notes are internal.** Under default-deny, no provider endpoint returns a call or a note.
- **No model in a handler.** Ending a call starts the notes as a background job; the client polls.

## Routes

| Method and path | Body | Returns |
|---|---|---|
| `GET /api/matters/{matter_id}/calls/next` | | `CallTargetOut[]`: who to call next |
| `POST /api/matters/{matter_id}/call-numbers` | `CallNumberIn` | `CallTargetOut`: a typed number, stored in Clarity (D15) |
| `POST /api/matters/{matter_id}/calls` | `CallStartIn` | `CallOut` |
| `PUT /api/calls/{call_id}/transcript` | `CallTranscriptIn` | `CallOut` |
| `POST /api/calls/{call_id}/end` | | `CallOut`; starts the notes job |
| `GET /api/calls/{call_id}` | | `CallDetailOut` |
| `GET /api/matters/{matter_id}/calls` | | `CallOut[]`, newest first |

## Models

```
CallTargetOut
  target_id: str                 # "contact:<clio id>" or "entered:<id>"
  name: str | None
  role: "client" | "provider" | "insurer" | "other"
  phone: str | None              # None: no number on file; the UI offers to type one
  phone_source: "clio" | "entered" | None
  reason: str | None             # the open item that makes this call due, in a few words
  reason_fact: FactRef | None    # that item's source, for its chip
  last_contact_days: int | None  # None means no contact found, never zero
  last_contact_fact: FactRef | None  # the communication behind last_contact_days, for its chip (rule 3, D23)

CallNumberIn
  name: str                      # who the number belongs to, as the attorney types it
  phone: str

CallStartIn
  target_id: str
  consent_confirmed: bool        # must be true; 422 otherwise
  consent_text: str              # the wording the attorney confirmed

CallTranscriptIn
  text: str                      # the whole transcript so far; the client saves every few seconds
  final: bool                    # true once the call has ended

CallOut
  call_id: int
  target: CallTargetOut
  started_at: datetime
  ended_at: datetime | None
  consent_text: str
  notes_status: "not_started" | "running" | "done" | "failed" | "no_model"

CallNoteOut
  fact: FactRef                  # the stored fact; its source is the transcript
  kind: "summary" | "commitment" | "date" | "amount" | "follow_up"
  text: str
  quote_start: int               # character offsets into the transcript
  quote_end: int

CallDetailOut
  call: CallOut
  transcript: str
  notes: list[CallNoteOut]
```

`notes_status` is `no_model` when the model settings are missing. The UI then shows the transcript alone and says why, and nothing pretends notes exist.

## The source drawer

A call note's fact opens its call in the drawer: `/api/facts/{fact_id}/source` returns the transcript as the source's text, with the note's quote highlighted, the same way notes and emails work today.
