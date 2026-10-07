"""Lenient models over the raw Clio JSON stored in `sources.raw_json`.

Only the fields the views read. Every field is optional: a record missing one still
renders, with that part left blank. Types are written `dt.date` because some Clio
fields are themselves named `date`, which would shadow the type in the class body.
"""

import datetime as dt

from pydantic import BaseModel


class Named(BaseModel):
    id: int | str | None = None
    name: str | None = None


class Url(BaseModel):
    url: str | None = None


class CustomFieldValue(BaseModel):
    field_name: str | None = None
    field_type: str | None = None  # Clio's type, such as "currency", "date", "checkbox"
    value: str | int | float | bool | None = None


class RawMatter(BaseModel):
    display_number: str | None = None
    description: str | None = None
    status: str | None = None
    open_date: dt.date | None = None
    close_date: dt.date | None = None
    client: Named | None = None
    responsible_attorney: Named | None = None
    practice_area: Named | None = None
    matter_stage: Named | None = None
    custom_field_values: list[CustomFieldValue] = []


class RawContact(BaseModel):
    name: str | None = None
    avatar: Url | None = None


class RawNote(BaseModel):
    subject: str | None = None
    detail: str | None = None
    date: dt.date | None = None
    author: Named | None = None


class RawCommunication(BaseModel):
    subject: str | None = None
    body: str | None = None
    date: dt.date | None = None
    senders: list[Named] = []


class RawTask(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    due_at: dt.datetime | dt.date | None = None
    completed_at: dt.datetime | dt.date | None = None
    statute_of_limitations: bool | None = None
    assignee: Named | None = None


class RawCalendarEntry(BaseModel):
    summary: str | None = None
    description: str | None = None
    location: str | None = None
    start_at: dt.datetime | dt.date | None = None


class RawActivity(BaseModel):
    type: str | None = None
    note: str | None = None
    date: dt.date | None = None


class RawDocument(BaseModel):
    name: str | None = None
    filename: str | None = None
    # The document's own date in Clio, as against `created_at`, the upload. Synced only
    # once DOCUMENT_FIELDS asks for it.
    received_at: dt.datetime | None = None


class RawRelationship(BaseModel):
    description: str | None = None
    contact: Named | None = None
