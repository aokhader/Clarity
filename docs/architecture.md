# Architecture

## Shape

```
Clio Manage (read-only)
      |
  Sync worker        pulls raw records and files, tracks ETags
      |
  Digest pipeline    pages -> facts -> brief, calls the models
      |
  Fact store         SQLite: facts with sources and visibility
      |
  API                auth stub, visibility filter
    /    \
Firm      Provider
view      view
```

One store of sourced facts feeds both views. The provider view is the same data behind a stricter filter, so it is cheap to build once the fact store exists.

## Components

**Sync worker (`clio/`).** Finds the matter, pulls every related record and document, and writes them to `sources`. Stores each record's ETag and Clio `updated_at`. A re-run fetches only what changed. Runs from the CLI or `POST /api/ops/sync`, never during a page load. Details in `docs/clio-api.md`.

**Digest pipeline (`digest/`).** Turns sources into facts in three passes: code-only mapping for structured records, model extraction for free text and PDF pages, then a merge pass that scores significance and writes the brief. Details in `docs/digest-pipeline.md`.

**Fact store (`models.py`).** The center of the design. One row per claim, each carrying its source, a visibility tag, and a significance score.

**API (`api/` and `services/`).** Read endpoints for the two views, plus share management and ops triggers. Handlers in `api/` are thin; queries and the visibility filter live in `services/`. All filtering happens on the server.

**Frontend.** A React SPA with two route trees: `/matters/:id` for the firm and `/p/:token` for providers.

## Data model

SQLite at `data/app.db`. No migrations: tables are created at startup, and `cli reset` drops everything. Changing a table means running reset, sync, and digest again, so settle the schema early.

```
sources
  id, matter_id, clio_type, clio_id, etag, clio_created_at, clio_updated_at,
  raw_json, file_path, content_hash, synced_at
  unique (clio_type, clio_id)
  clio_type: matter | contact | relationship | note | communication | task |
             calendar_entry | activity | document

pages
  id, source_id, page_no, has_text_layer, text, image_path, content_hash,
  extracted_at

facts
  id, matter_id, kind, title, value_json, event_date,
  source_id, page_no, quote,
  provider_contact_id,        -- Clio contact this fact concerns, if any
  visibility,                 -- internal | shareable
  significance,               -- 0 to 100
  confidence,                 -- high | medium | low
  verified,                   -- passed the checks in verify.py
  origin,                     -- code | model
  created_at

digests
  id, matter_id, kind, content_json, input_hash, model, created_at
  kind: brief | field_mapping

llm_calls
  id, purpose, model, input_tokens, output_tokens, cost_usd,
  source_id, page_no, cache_hit, created_at

users
  id, name, role              -- stub accounts, see Auth

views
  user_id, matter_id, last_opened_at

shares
  id, token, matter_id, provider_contact_id, settings_json,
  hidden_fact_ids_json, note, created_by, created_at, expires_at, revoked_at

share_events
  id, share_id, event, created_at     -- event: opened

sync_runs
  id, started_at, finished_at, stats_json, error

oauth_tokens
  id, access_token, refresh_token, expires_at
```

How features fall out of the schema:

- Click-to-source: `facts.source_id`, `page_no`, `quote`
- The ten that matter: order by `significance`
- What changed: facts whose source has `clio_created_at` or `clio_updated_at` later than `views.last_opened_at`
- Has anyone opened it: `share_events`
- Adjust before sending: `shares.settings_json` and `hidden_fact_ids_json`
- Cost per case: sum of `llm_calls.cost_usd` where `cache_hit` is false

## Fact kinds

```
case_stage        status_change      injury            diagnosis
treatment_visit   medical_bill       lien              records_received
record_request    coverage           policy_limit      case_value
liability         demand             offer             settlement
expense           deadline           task              client_contact
party             other
```

`title` is the short display string, generated at extraction time. `value_json` holds the kind-specific payload below. These payloads are the contract between the pipeline and the two views, so define them as Pydantic models in `schemas.py` during M0. Money is integer cents.

| Kind | `value_json` keys |
|---|---|
| `case_stage` | `stage`, `inferred` |
| `status_change` | `from_stage`, `to_stage`, `label` |
| `injury`, `diagnosis` | `body_part`, `description`, `severity` |
| `treatment_visit` | `visit_type` |
| `medical_bill`, `lien` | `amount_cents`, `balance_cents` |
| `records_received` | `description`, `page_count` |
| `record_request` | `description`, `status` (open or fulfilled) |
| `coverage` | `carrier`, `coverage_type`, `confirmed` |
| `policy_limit` | `amount_cents`, `per` (person or occurrence) |
| `case_value` | `low_cents`, `high_cents`, `basis` |
| `liability` | `assessment` |
| `demand`, `offer`, `settlement` | `amount_cents`, `party` |
| `expense` | `amount_cents`, `category`, `vendor` |
| `deadline` | `deadline_type`, `due_at` |
| `task` | `status`, `due_at`, `assignee`, `waiting_on` (firm, client, provider, insurer, court, other) |
| `client_contact` | `channel`, `direction` |
| `party` | `role` |

Any payload may also carry `alt_values` (when two reads or two sources disagree) and `corroborating_source_ids`.

## Visibility

Visibility is decided by code from `kind` and `provider_contact_id`. A model never decides it alone. The rule is default-deny: a kind missing from the allowlist is internal.

| Share setting | Default | Facts it releases |
|---|---|---|
| `case_stage` | on | `case_stage`, `status_change` (date and neutral label only), whether the matter is open |
| `coverage_exists` | on | A boolean derived from `coverage` facts. No carrier, no amounts. |
| `coverage_limits` | off | `policy_limit` amounts |
| `own_bills` | on | `medical_bill`, `lien` where `provider_contact_id` matches the share |
| `own_records` | on | `records_received` where `provider_contact_id` matches |
| `requests` | on | `record_request` and open `task` facts where `provider_contact_id` matches |
| `treatment_activity` | off | Month of the most recent `treatment_visit` across providers, with no provider named |

Never shareable under any setting: `case_value`, `liability`, `demand`, `offer`, `expense`, `client_contact`, internal notes, and any fact the extractor flagged `mentions_strategy`.

A provider response is the intersection of four tests: the kind is released by an enabled setting, the provider match holds where required, the fact is not in `hidden_fact_ids_json`, and the share is neither expired nor revoked. Implement it as one function, `visible_facts_for_share(share)`, and test it. This function is the security boundary of the product.

Source access follows the same rule: a provider may open the source of a fact only if that fact is visible to them, and only for `own_bills` and `own_records` kinds. Case-level facts show no source to providers, since the source may be an internal note.

## API routes

Firm routes take the stub user from an `X-User-Id` header.

```
GET   /api/matters                               list matters from sources
GET   /api/matters/{id}                          header: client, stage, KPIs, last client contact
GET   /api/matters/{id}/brief                    narrative with fact ids per sentence
GET   /api/matters/{id}/changes                  facts new since this user's last open
POST  /api/matters/{id}/opened                   record the visit
GET   /api/matters/{id}/feed?limit=10            facts by significance
GET   /api/matters/{id}/timeline?kind=&q=        all facts by date
GET   /api/matters/{id}/actions                  overdue, upcoming, waiting on others
GET   /api/matters/{id}/injuries
GET   /api/matters/{id}/providers                provider contacts, totals, share status

GET   /api/facts/{id}/source                     source record, quote, page image url
GET   /api/pages/{id}/image                      rendered page PNG

GET   /api/matters/{id}/shares
POST  /api/matters/{id}/shares                   create for a provider contact
GET   /api/shares/{id}/preview                   exactly what the provider would get
PATCH /api/shares/{id}                           settings, hidden facts, note, expiry
POST  /api/shares/{id}/revoke

POST  /api/ops/sync            GET /api/ops/sync/status
POST  /api/ops/digest          GET /api/ops/digest/status
GET   /api/ops/cost                              tokens and dollars for this matter
```

Provider routes take no header. The token is the credential.

```
GET   /api/p/{token}                             provider payload, records an opened event
GET   /api/p/{token}/facts/{id}/source           only for visible own-bill and own-record facts
```

`/api/shares/{id}/preview` and `/api/p/{token}` must call the same function so the preview cannot drift from what the provider gets.

## Change detection and caching

- Sync compares ETags and skips unchanged records.
- Pages are keyed by `content_hash`. Extraction skips a page whose hash already has facts.
- The brief stores an `input_hash` over the fact set it was built from and is rebuilt only when that hash changes.
- Every model call goes through `digest/llm.py`, which checks the cache first and logs to `llm_calls`.

## Auth

There is no real authentication, and the submission form must say so.

- Firm users are seeded stub accounts with generic names and roles. A user switcher in the header sets `X-User-Id`. Seeded `last_opened_at` values differ per user so the "since you last opened" block has something to show. Log this in the stubs section of `docs/progress.md`.
- Provider access is a random URL-safe token of at least 32 bytes, checked for expiry and revocation on every request.

## Configuration

All configuration comes from environment variables read in `config.py`. See `.env.example`. Nothing else reads `os.environ`.

## Failure handling

- Sync and digest record per-item errors and continue. One unreadable PDF must not stop the run.
- The firm view renders whatever facts exist and shows a banner when the last sync or digest had errors.
- On a Clio 429, wait for `Retry-After` and retry.
- If a KPI has no supporting fact, show "Not found in file" with no number. Never show a guess.
