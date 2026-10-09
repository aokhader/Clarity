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

SQLite at `data/app.db`. Tables are created at startup, and there are no migrations. A new table is simply created. A new fact kind or source type widens an enum's CHECK constraint, which SQLite cannot alter. `db.upgrade_schema()` therefore rebuilds each such table in place, copying every row, after backing the database up beside itself (D24). `cli upgrade-schema` runs it with the API stopped, and `cli seed-dev` runs it itself. Any other change to an existing column still means `cli reset`, sync and digest, so the columns were settled early. `cli reset` drops everything, and refuses while `data/` holds backups.

`matter_id` is the Clio matter id. `file_path` and `image_path` are stored relative to `DATA_DIR`, so a zipped `data/` snapshot works on another machine.

```
sources
  id, matter_id, clio_type, clio_id, etag, clio_created_at, clio_updated_at,
  raw_json, file_path, content_hash, synced_at
  unique (matter_id, clio_type, clio_id)   -- account-level records (contacts, custom
                                           -- fields) get one copy per matter
  clio_id is a string: calendar entry ids are strings in Clio
  clio_type: matter | custom_field | contact | relationship | note | communication |
             task | calendar_entry | activity | document |
             call          -- not a Clio record: a call placed from Clarity, whose
                           -- transcript its notes cite (D8)

pages
  id, source_id, page_no, has_text_layer, text, image_path, content_hash,
  extracted_at

facts
  id, matter_id, kind, title, value_json, event_date,
  source_id, page_no, quote,
  provider_contact_id,        -- Clio contact this fact concerns, if any
  mentions_strategy,          -- extractor flag; such a fact is never shareable
  visibility,                 -- internal | shareable
  significance,               -- 0 to 100
  confidence,                 -- high | medium | low
  verified,                   -- passed the checks in verify.py
  origin,                     -- code | model
  created_at

digests
  id, matter_id, kind, content_json, input_hash, model, created_at
  kind: brief | field_mapping

llm_calls                             -- also the response cache, keyed by cache_key
  id, matter_id, purpose, model, cache_key, response_json,
  input_tokens, output_tokens, cost_micro_usd,   -- integer micro-dollars, exact sums
  source_id, page_no, cache_hit, error, created_at

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
  id, matter_id, started_at, finished_at, stats_json, error

digest_runs                           -- same shape, so the UI can flag a failed digest
  id, matter_id, started_at, finished_at, stats_json, error

oauth_tokens
  id, access_token, refresh_token, expires_at

call_numbers                          -- a number typed in the Calls view, kept in
  id, matter_id, name, phone, created_at   -- Clarity only, never written to Clio (D15)

calls
  id, matter_id, target_json, consent_text, started_at, ended_at,
  transcript, transcript_final, notes_status, notes_error,
  source_id                           -- the `call` source its notes cite
```

The Calls tables and routes are specified in `docs/calls-contract.md`.

How features fall out of the schema:

- Click-to-source: `facts.source_id`, `page_no`, `quote`
- The ten that matter: order by `significance`
- The story so far: dated past events, oldest first, a few per kind (D39)
- What changed: facts whose source has `clio_created_at` or `clio_updated_at` later than `views.last_opened_at`
- Has anyone opened it: `share_events`
- Adjust before sending: `shares.settings_json` and `hidden_fact_ids_json`
- Cost per case: sum of `llm_calls.cost_micro_usd` for the matter where `cache_hit` is false

## Fact kinds

```
case_stage        status_change      injury            diagnosis
treatment_visit   medical_bill       lien              records_received
record_request    coverage           policy_limit      case_value
liability         demand             offer             settlement
expense           deadline           task              client_contact
party             incident           medical_specials  economic_damages
recovery_cap      call_note          litigation_event  other
```

- **`incident` and `medical_specials`** come from mapped custom fields and feed the header and the KPI strip. Records that describe the incident also yield model `incident` facts. The header's incident account is the one most of them give, never the custom field's label (D39).
- **`economic_damages` and `recovery_cap`** have kinds of their own (D20). Before that they were filed as specials or case value, which they are not.
- **`call_note`** is a note taken from a call's transcript (D8).
- **`litigation_event`** is something that happened in the lawsuit: a filing, service, an answer, a dismissal, a refiling, a motion, an order, or a hearing, deposition or trial that took place (D41). It is dated by the date the record gives for the event, never by the date of the note that reports it.
- **`status_change`** is meant for a move between stages, with `to_stage` set. The extraction prompts file court events as `litigation_event` instead, and a provider sees only the status changes that name a stage (D41).

`title` is the short display string, generated at extraction time. `value_json` holds the kind-specific payload below. These payloads are the contract between the pipeline and the two views, so define them as Pydantic models in `schemas.py` during M0. Money is integer cents.

| Kind | `value_json` keys |
|---|---|
| `case_stage` | `stage` (canonical: intake, treating, treatment_complete, demand, negotiation, litigation, settled, closed), `inferred` |
| `status_change` | `from_stage`, `to_stage`, `label` (the record's wording, shown to the firm only, D41) |
| `injury`, `diagnosis` | `body_part`, `description`, `severity` |
| `treatment_visit` | `visit_type` |
| `medical_bill`, `lien` | `amount_cents`, `balance_cents` |
| `records_received` | `description`, `page_count` |
| `record_request` | `description`, `status` (open or fulfilled) |
| `coverage` | `carrier`, `coverage_type`, `confirmed` |
| `policy_limit` | `amount_cents`, `per` (person or occurrence), `policy` (defendant_liability, client_no_fault, client_um_uim, client_other, or null when the file does not say; D19, D21) |
| `case_value` | `low_cents`, `high_cents`, `basis` |
| `liability` | `assessment` |
| `demand`, `offer`, `settlement` | `amount_cents`, `party` |
| `expense` | `amount_cents`, `category`, `vendor` |
| `deadline` | `deadline_type`, `due_at`, `status` (open or complete: the status of the Clio task it was read from, filled when served, so a met statute is not shown as passed; D40) |
| `task` | `status`, `due_at`, `assignee`, `waiting_on` (firm, client, provider, insurer, court, other) |
| `client_contact` | `channel`, `direction` |
| `party` | `role` |
| `incident` | `description` |
| `medical_specials` | `amount_cents` |
| `economic_damages`, `recovery_cap` | `amount_cents`, `basis` (what the total includes, or what sets the cap) |
| `call_note` | `note_kind` (summary, commitment, date, amount, follow_up), `quote_start`, `quote_end` (the span of the transcript it quotes), `amounts_cents`, `dates` |
| `litigation_event` | `event` (filed, served, answered, dismissed, renewed, motion, order, hearing, deposition, trial, other), `detail` |
| `other` | `detail` |

Any payload may also carry `alt_values` (when two reads or two sources disagree) and `corroborating_source_ids`. `PAYLOAD_BY_KIND` in `schemas.py` is the authority; `validate_payload` rejects unknown keys, so the pipeline calls it before storing a fact.

## Visibility

Visibility is decided by code from `kind` and `provider_contact_id`. A model never decides it alone. The rule is default-deny: a kind missing from the allowlist is internal.

| Share setting | Default | Facts it releases |
|---|---|---|
| `case_stage` | on | `case_stage`, whether the matter is open, and each `status_change` that moves to a named stage (`to_stage` set). A provider sees the move's date and a label written in code, such as "Moved to litigation", never the record's own wording, which can name what the firm keeps (D41) |
| `coverage_exists` | on | A boolean derived from `coverage` facts. No carrier, no amounts. |
| `coverage_limits` | off | `policy_limit` amounts of the defendant's liability policy only (`policy` is `defendant_liability`, D37), each labelled per person or per occurrence. The client's own policies and limits with no policy are never released. |
| `own_bills` | on | `medical_bill`, `lien` where `provider_contact_id` matches the share. A lien is labelled as one and kept out of the bills total (D35) |
| `own_records` | on | `records_received` where `provider_contact_id` matches |
| `requests` | on | `record_request` and open `task` facts where `provider_contact_id` matches |
| `treatment_activity` | off | Month of the most recent `treatment_visit` across providers, with no provider named |

Never shareable under any setting, because no setting releases their kind: `case_value`, `liability`, `demand`, `offer`, `settlement`, `expense`, `client_contact`, `economic_damages`, `recovery_cap`, `call_note`, `litigation_event`, and every other kind missing from the table. A fact the extractor flagged `mentions_strategy` is never shareable, whatever its kind. The rules live in `services/visibility.py` (`KINDS_BY_SETTING`, `is_stage_move`, `is_shared_limit`).

A provider response is the intersection of four tests: the kind is released by an enabled setting, the provider match holds where required, the fact is not in `hidden_fact_ids_json`, and the share is neither expired nor revoked. Implement it as one function, `visible_facts_for_share(share)`, and test it. This function is the security boundary of the product.

Source access follows the same rule: a provider may open the source of a fact only if that fact is visible to them, and only for `own_bills` and `own_records` kinds. Case-level facts show no source to providers, since the source may be an internal note.

## API routes

Firm routes take the stub user from an `X-User-Id` header.

```
GET   /api/users                                 stub accounts for the user switcher
GET   /api/matters                               list matters from sources
GET   /api/matters/{id}                          header: client, stage, KPIs, last client contact
GET   /api/matters/{id}/brief                    narrative with fact ids per sentence
GET   /api/matters/{id}/changes                  facts new since this user's last open
POST  /api/matters/{id}/opened                   record the visit
GET   /api/matters/{id}/feed?limit=10            facts by significance
GET   /api/matters/{id}/key-events?limit=10      the story so far: the incident, up to three
                                                 dated court events by type, then other dated
                                                 past events; oldest first (D39, D43)
GET   /api/matters/{id}/key-events/undated       court events no record dates, leaving out
                                                 any a dated record restates (D43)
GET   /api/matters/{id}/timeline?kind=&q=        all facts by date
GET   /api/matters/{id}/actions                  overdue, upcoming, waiting_on_others (shown
                                                 as "open requests", D40)
GET   /api/matters/{id}/injuries
GET   /api/matters/{id}/providers                provider contacts, totals, share status

GET   /api/facts/{id}/source                     source record, quote, pages with their text
GET   /api/pages/{id}/image                      rendered page PNG

GET   /api/matters/{id}/shares
POST  /api/matters/{id}/shares                   create for a provider contact
POST  /api/matters/{id}/shares/preview           what a share would release, before it exists
POST  /api/matters/{id}/shares/draft-check       the draft checker, before the link exists
GET   /api/shares/{id}/preview                   exactly what the provider would get
POST  /api/shares/{id}/draft-check               each sentence's amounts and dates against
                                                 what this link shows and withholds (D2)
PATCH /api/shares/{id}                           settings, hidden facts, note, expiry
POST  /api/shares/{id}/revoke

GET   /api/matters/{id}/calls/next               who to call next, with phone numbers (D8)
POST  /api/matters/{id}/call-numbers             a typed number, stored only in Clarity
POST  /api/matters/{id}/calls                    start a call, with the consent logged
GET   /api/matters/{id}/calls
PUT   /api/calls/{id}/transcript                 save the transcript
POST  /api/calls/{id}/end                        end the call and start the notes run
GET   /api/calls/{id}                            the call, its notes and their status

GET   /api/ops/health                            API and database up; whether .env is filled
POST  /api/ops/sync            GET /api/ops/sync/status
POST  /api/ops/digest          GET /api/ops/digest/status   (body: retry_failed)
GET   /api/ops/cost                              tokens and dollars for this matter
```

No GET route calls a model. A digest and a call's notes start a background run from a POST and are stored; the routes then serve the stored result.

Provider routes take no header. The token is the credential.

```
GET   /api/p/{token}                             provider payload, records an opened event
GET   /api/p/{token}/facts/{id}/source           only for visible own-bill and own-record facts
GET   /api/p/{token}/pages/{id}/image            only the cited page of such a fact
```

`/api/shares/{id}/preview` and `/api/p/{token}` must call the same function so the preview cannot drift from what the provider gets.

Request and response models for every route are in `backend/app/schemas.py`, mirrored in `frontend/src/api/types.ts`. Backend owns both and changes them in one commit. The routers are `api/matters.py`, `api/facts.py`, `api/shares.py` (including `/api/matters/{id}/providers`), `api/provider.py`, `api/calls.py` and `api/ops.py`. During the hackathon they were split by track (`docs/parallel.md`); in the kit trial backend owns them all.

## Change detection and caching

- Sync compares ETags and skips unchanged records.
- Pages are keyed by `content_hash`. Extraction skips a page whose hash already has facts.
- The brief stores an `input_hash` over the fact set it was built from and is rebuilt only when that hash changes.
- Every model call goes through `digest/llm.py`, which checks the cache first and logs to `llm_calls`.
- A prompt's version string is part of each call's cache key, so a changed prompt misses the cache only for the inputs it reads. `cli reextract --page/--record` re-reads chosen inputs alone, and `--dry-run` prices them first. Each paid run follows the D34 runbook: an estimate, a trial on a copy of the database, a backup, then the run against a cost stop.

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
