# Clio Manage API

Clio is the input and nothing else. Read everything, write nothing.

## What is verified and what is not

The endpoint table and the client requirements were checked against Clio's OpenAPI spec, saved in `docs/reference/clio-openapi.json` (OpenAPI 3.0.0, `info.version` `v4`; the default minor version it lists is 4.0.13). Paths, query parameters, and field names in the table are confirmed there. The spec was published at `https://docs.developers.clio.com/openapi.json`. It is several megabytes, so query it with a script or `grep` and never read it whole into context.

The spec does not describe rate limits, paging, or the `fields` syntax; it links to Clio's published documentation for those. These points come from that documentation, checked on October 2, 2026, and not from the spec:

- Default rate limit is 50 requests per minute per access token during peak hours (04:00 to 19:00 Pacific on weekdays for US accounts). Responses carry `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset`. A 429 carries `Retry-After`. The spec lists a 429 response with an `error` body but no headers.
- Without a `fields` parameter most endpoints return only `id` and `etag`.

Confirmed in the spec:

- Every list endpoint used here accepts `fields`, `limit` (1 to 200, default 200), `page_token`, `ids[]`, `created_since`, and `updated_since` (ISO-8601 timestamps).
- `/notes.json` requires `type`, one of `Matter` or `Contact`.
- `/activities.json` accepts `type`, one of `TimeEntry`, `ExpenseEntry`, `HardCostEntry`, `SoftCostEntry`, `FixedFee`.
- `order` defaults to `id(asc)`, except `/communications.json`, which defaults to `date(asc)`. `/relationships.json` and `/calendar_entries.json` do not accept `order`.
- A bare nested field returns only its `id`: the spec's own example requests `custom_field_values{id,value,custom_field}` and gets `custom_field: { id: 2 }`. Always name the subfields you need.
- Custom field values: `field_name` is the display name, carried on each value. The value's `id` is a composite string such as `text_line-1` and is null when a displayed field has no value yet, so key on `custom_field.id`. `value` is typed as a string. For picklists the label is `option` on the picklist option, resolved through `/custom_fields.json`.
- `CalendarEntry.id` and `CustomFieldValue.id` are strings; every other `id` used here is an integer.
- Money fields (`total`, `price`, `amount`) are JSON numbers. Convert them to `Decimal` at parse time.

Not confirmed by the spec:

- The `meta.paging.next` envelope, and whether `order` affects paging. The spec's list schemas define only `data`.
- The rate-limit headers and `Retry-After`.
- Whether `/documents.json?matter_id=` includes documents in subfolders of the matter's folder. The `scope` parameter (`children` or `descendants`) is documented only together with `parent_id`.
- Whether a field nested two levels deep (for example `picklist_option{option}` inside `custom_field_values{...}`) is accepted. The table avoids it.
- For picklist custom fields, whether `value` holds the option id or its label.

### Corrections from the spec

- Matter `custom_field_values{id,field_name,value}` -> `custom_field_values{id,field_name,field_type,value,custom_field,picklist_option}`, to get a stable `custom_field.id` and the picklist option id.
- Contact `custom_field_values{field_name,value}` -> the same subfields as the matter.
- Contact `addresses` -> `addresses{name,street,city,province,postal_code,country}`, since a bare nested field returns only `id`.
- New row: custom field definitions from `/custom_fields.json`, the only place picklist labels live.
- Notes: added `detail_text_type`, because `detail` may be rich text.
- Communications: added `received_at`, because `date` is a date only.
- Tasks: added `statute_of_limitations` (a boolean on the task).
- Calendar: added `owner_entries_across_all_users=true`, which the spec describes as returning entries for all users related to the matter. Users otherwise see only entries on calendars they can view.
- Activities: added `non_billable,non_billable_total`, because `total` covers only draft, billable, and billed amounts.
- Documents: added `filename` (for the file extension) and `latest_document_version{filename,fully_uploaded}`.
- Document download: the optional `document_version_id` parameter exists and defaults to the latest version.
- Notes `type`: the spec makes it required, not only validated.
- Paths: all eleven paths exist with a GET operation and the `.json` suffix, relative to the `/api/v4` base. None changed.

## Base URL and auth

- US base URL: `https://app.clio.com/api/v4`. The spec also lists `eu.`, `ca.`, and `au.app.clio.com`. Paths in the table are relative to this base.
- OAuth 2.0 authorization-code flow. Register a developer application in Clio's developer portal with redirect URI `http://127.0.0.1:8000/oauth/callback` and read-only permissions for every resource below.
- Authorize: `GET https://app.clio.com/oauth/authorize?response_type=code&client_id=...&redirect_uri=...&state=...`
- Token: `POST https://app.clio.com/oauth/token` with `grant_type=authorization_code` (later `refresh_token`)
- Requests: `Authorization: Bearer <access_token>`
- `python -m app.cli auth` prints the authorize URL, receives the callback on the running server, and stores both tokens in `oauth_tokens`. Refresh automatically on a 401.

A missing permission shows up as a 403 on that one endpoint. Report it; do not work around it.

## Endpoints to pull

All GET. Scope by `matter_id` once the matter is found. Custom field definitions are account-wide and take no matter filter.

| Data | Path | Fields to request |
|---|---|---|
| Find the matter | `/matters.json?query={CLIO_MATTER_QUERY}` | `id,display_number,description` |
| Matter | `/matters/{id}.json` | `id,etag,display_number,description,status,open_date,close_date,practice_area{name},matter_stage{name},client{id,name},responsible_attorney{name},custom_field_values{id,field_name,field_type,value,custom_field,picklist_option},created_at,updated_at` |
| Custom field definitions | `/custom_fields.json` | `id,etag,name,field_type,parent_type,picklist_options{id,option},updated_at` |
| Relationships | `/relationships.json?matter_id={id}` | `id,etag,description,contact{id,name,type},created_at,updated_at` |
| Contacts | `/contacts.json?ids[]=...` | `id,etag,name,type,title,email_addresses{address,name},phone_numbers{number,name},addresses{name,street,city,province,postal_code,country},custom_field_values{id,field_name,field_type,value,custom_field,picklist_option},avatar{url},updated_at` |
| Notes | `/notes.json?type=Matter&matter_id={id}` | `id,etag,subject,detail,detail_text_type,date,author{name},created_at,updated_at` |
| Communications | `/communications.json?matter_id={id}` | `id,etag,subject,body,type,date,received_at,senders{id,name,type},receivers{id,name,type},created_at,updated_at` |
| Tasks | `/tasks.json?matter_id={id}` | `id,etag,name,description,status,priority,due_at,completed_at,statute_of_limitations,assignee{id,name,type},created_at,updated_at` |
| Calendar | `/calendar_entries.json?matter_id={id}&owner_entries_across_all_users=true` | `id,etag,summary,description,location,start_at,end_at,all_day,created_at,updated_at` |
| Expenses | `/activities.json?matter_id={id}` | `id,etag,type,date,total,price,quantity,non_billable,non_billable_total,note,expense_category{name},vendor{id,name},created_at,updated_at` |
| Documents | `/documents.json?matter_id={id}` | `id,etag,name,filename,content_type,size,created_at,updated_at,latest_document_version{id,size,content_type,filename,fully_uploaded}` |
| Document file | `/documents/{id}/download.json` | No `fields`. Returns 303 See Other to the file's URL. Optional `document_version_id`, defaulting to the latest version. |

Notes:

- Provider identification depends on the relationship `description` (for example a treating-provider label). Do not match on specific label strings in code. The merge step classifies relationship descriptions into roles with a model call; see `docs/digest-pipeline.md`.
- Pull all activity types and separate them by `type`. Firm spend is the sum of the non-time types, counting `total` plus `non_billable_total`.
- Custom field names are configured per firm. Never reference a field by name in code.
- The Clio screenshots in the brief show Medical Records, Damages, and Settlement tabs. The brief's own list of loaded data does not mention them. Check in the account whether they hold data before building against them. The endpoints the spec offers are below.

### Personal-injury endpoints

The spec has read endpoints for the Medical Records and Damages tabs and none for Settlement. Neither list endpoint accepts `matter_id`, so the sync must page through the account's records and keep those whose `matter.id` matches. `updated_since` works on both.

| Data | Path | Fields to request |
|---|---|---|
| Medical records details (each names one `medical_provider`) | `/medical_records_details.json` | `id,etag,description,in_treatment,treatment_start_date,treatment_end_date,records_status,records_request_date,records_follow_up_date,bills_status,bills_request_date,bills_follow_up_date,matter{id},medical_provider{id,name,type},medical_records{id,document_id,start_date,end_date},medical_bills{id,name,amount,adjustment,bill_date,bill_received_date,damage_type,document_id},created_at,updated_at` |
| Damages | `/damages.json` | `id,etag,amount,damage_type,description,matter{id},created_at,updated_at` |

- The list endpoints also accept `ids[]`, `limit`, `page_token`, and `created_since`. `/medical_records_details.json` also filters on `treatment_start_date` and `treatment_end_date`. Neither accepts `order`.
- `records_status` and `bills_status` are one of `not_yet_requested`, `requested`, `received`, `incomplete`, `certified`. `damage_type` on a damage is one of `special`, `general`, `other`; on a medical bill it is a free string.
- `document_id` on a medical record or bill links to a document from `/documents.json`.
- Liens are not readable as far as the spec shows. The full medical bill schema has `liens` (`amount`, `description`, `lien_type` of `general`, `medical_payer`, or `medical_provider`), but `/medical_bills/{id}.json` has no GET, and the bills nested in a medical records detail use a schema without `liens`. The create payload accepts a bill `balance` that no read schema returns.
- `/medical_records/{id}.json` and `/medical_bills/{id}.json` offer only PATCH and DELETE. Do not call them.

## Client requirements (`clio/client.py`)

1. **GET only.** The client has one request method that sends GET. Add a guard that raises `ClioWriteForbidden` if any other verb is attempted, and a test for it.
2. **Fields always.** Every call passes an explicit `fields` string, defined as a constant beside the call.
3. **Paging.** Pass `limit=200`. Follow `meta.paging.next` as an opaque URL until it is absent. Response bodies are wrapped as `{"data": ..., "meta": ...}`; the spec defines `data` only, so check the `meta` shape on the first real response. Do not pass `order` by default: two endpoints in the table do not accept it, and the defaults are stable.
4. **Rate limiting.** Read `X-RateLimit-Remaining` and sleep until `X-RateLimit-Reset` when it reaches zero. On 429, sleep for `Retry-After` and retry. Document downloads count toward the limit. Headers come from the published docs; the spec lists only the 429 status and its `error` body.
5. **Downloads.** Request the download path without following redirects, read the `Location` of the 303, and fetch that URL with a separate request that does not carry the Clio `Authorization` header. Stream to `data/files/{clio_id}{ext}`, taking `{ext}` from `filename`.
6. **Incremental.** Store `etag`, `created_at`, and `updated_at` on every record. On re-sync, pass `updated_since` (every list endpoint here accepts it) and skip records whose ETag is unchanged. List endpoints never return 304, so that comparison happens in our code. Single-record endpoints such as `/matters/{id}.json` accept `IF-NONE-MATCH` with the stored ETag and answer 304 Not Modified when nothing changed.
7. **Raw first.** Store the response JSON untouched in `sources.raw_json`. Parsing happens in the digest pipeline, so a parsing bug never requires another sync.
8. **Pinned version.** Send `X-API-VERSION` set from config (4.0.13, the spec's default), so a change of default minor version cannot change field meanings under us. Activity `quantity`, for example, changed from hours to seconds in 4.0.4.

## Sync order

1. Find the matter by query, then fetch it with full fields. Pull the custom field definitions.
2. Relationships, then the contacts they reference plus the client.
3. Notes, communications, tasks, calendar entries, activities.
4. Document list, then downloads.
5. Write a `sync_runs` row with counts per type and any errors.
