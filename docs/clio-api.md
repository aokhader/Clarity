# Clio Manage API

Clio is the input and nothing else. Read everything, write nothing.

## What is verified and what is not

Checked against Clio's published documentation on October 2, 2026:

- Default rate limit is 50 requests per minute per access token during peak hours (04:00 to 19:00 Pacific on weekdays for US accounts). Responses carry `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset`. A 429 carries `Retry-After`.
- Without a `fields` parameter most endpoints return only `id` and `etag`.
- List endpoints accept `limit` (1 to 200, default 200) and `page_token`.
- `/activities.json` accepts `matter_id`, `type` (`TimeEntry`, `ExpenseEntry`, `HardCostEntry`, `SoftCostEntry`, `FixedFee`), `updated_since`, and `created_since`.
- Querying notes validates a `type` parameter.
- Clio publishes an OpenAPI file at `https://docs.developers.clio.com/openapi.json`.

Everything else in this file (paths, filters, and especially field names) comes from general knowledge of API v4 and must be confirmed against the spec before the sync code depends on it. In M0, download the spec to `docs/reference/clio-openapi.json`. It is several megabytes, so query it with `jq` or `grep` and never read it whole into context.

## Base URL and auth

- US base URL: `https://app.clio.com/api/v4`
- OAuth 2.0 authorization-code flow. Register a developer application in Clio's developer portal with redirect URI `http://127.0.0.1:8000/oauth/callback` and read-only permissions for every resource below.
- Authorize: `GET https://app.clio.com/oauth/authorize?response_type=code&client_id=...&redirect_uri=...&state=...`
- Token: `POST https://app.clio.com/oauth/token` with `grant_type=authorization_code` (later `refresh_token`)
- Requests: `Authorization: Bearer <access_token>`
- `python -m app.cli auth` prints the authorize URL, receives the callback on the running server, and stores both tokens in `oauth_tokens`. Refresh automatically on a 401.

A missing permission shows up as a 403 on that one endpoint. Report it; do not work around it.

## Endpoints to pull

All GET. Scope by `matter_id` once the matter is found.

| Data | Path | Fields to request (confirm in spec) |
|---|---|---|
| Find the matter | `/matters.json?query={CLIO_MATTER_QUERY}` | `id,display_number,description` |
| Matter | `/matters/{id}.json` | `id,etag,display_number,description,status,open_date,close_date,practice_area{name},matter_stage{name},client{id,name},responsible_attorney{name},custom_field_values{id,field_name,value},created_at,updated_at` |
| Relationships | `/relationships.json?matter_id={id}` | `id,etag,description,contact{id,name,type},created_at,updated_at` |
| Contacts | `/contacts.json?ids[]=...` | `id,etag,name,type,title,email_addresses{address,name},phone_numbers{number,name},addresses,custom_field_values{field_name,value},avatar{url},updated_at` |
| Notes | `/notes.json?type=Matter&matter_id={id}` | `id,etag,subject,detail,date,author{name},created_at,updated_at` |
| Communications | `/communications.json?matter_id={id}` | `id,etag,subject,body,type,date,senders{id,name,type},receivers{id,name,type},created_at,updated_at` |
| Tasks | `/tasks.json?matter_id={id}` | `id,etag,name,description,status,priority,due_at,completed_at,assignee{id,name,type},created_at,updated_at` |
| Calendar | `/calendar_entries.json?matter_id={id}` | `id,etag,summary,description,location,start_at,end_at,all_day,created_at,updated_at` |
| Expenses | `/activities.json?matter_id={id}` | `id,etag,type,date,total,price,quantity,note,expense_category{name},vendor{id,name},created_at,updated_at` |
| Documents | `/documents.json?matter_id={id}` | `id,etag,name,content_type,size,created_at,updated_at,latest_document_version{id,size,content_type}` |
| Document file | `/documents/{id}/download.json` | Returns a 303 redirect to a signed URL |

Notes:

- Provider identification depends on the relationship `description` (for example a treating-provider label). Do not match on specific label strings in code. The merge step classifies relationship descriptions into roles with a model call; see `docs/digest-pipeline.md`.
- Pull all activity types and separate them by `type`. Firm spend is the sum of the non-time types.
- Custom field names are configured per firm. Never reference a field by name in code.
- The Clio screenshots in the brief show Medical Records, Damages, and Settlement tabs. The brief's own list of loaded data does not mention them. Check in the account whether they hold data before building against them, and look for matching paths in the spec.

## Client requirements (`clio/client.py`)

1. **GET only.** The client has one request method that sends GET. Add a guard that raises `ClioWriteForbidden` if any other verb is attempted, and a test for it.
2. **Fields always.** Every call passes an explicit `fields` string, defined as a constant beside the call.
3. **Paging.** Follow `meta.paging.next` until it is absent. Response bodies are wrapped as `{"data": ..., "meta": ...}`.
4. **Rate limiting.** Read `X-RateLimit-Remaining` and sleep until `X-RateLimit-Reset` when it reaches zero. On 429, sleep for `Retry-After` and retry. Document downloads count toward the limit.
5. **Downloads.** Request the download path, read the `Location` of the 303, and fetch that URL with a separate request that does not carry the Clio `Authorization` header. Stream to `data/files/{clio_id}{ext}`.
6. **Incremental.** Store `etag`, `created_at`, and `updated_at` on every record. On re-sync, pass `updated_since` where the endpoint supports it and skip records whose ETag is unchanged.
7. **Raw first.** Store the response JSON untouched in `sources.raw_json`. Parsing happens in the digest pipeline, so a parsing bug never requires another sync.

## Sync order

1. Find the matter by query, then fetch it with full fields.
2. Relationships, then the contacts they reference plus the client.
3. Notes, communications, tasks, calendar entries, activities.
4. Document list, then downloads.
5. Write a `sync_runs` row with counts per type and any errors.
