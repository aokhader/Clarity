# Digest pipeline

The pipeline turns `sources` into `facts` and a brief. Accuracy matters more than coverage: a wrong date in front of a trial attorney costs more than a missing one.

## Principles

- **Extract facts, not summaries.** Each fact is small, typed, and carries the quote it came from.
- **Code where code suffices.** A task's due date is already structured. No model call.
- **One page at a time for documents.** A whole 200-page scan in one call makes the model skim and lose page attribution.
- **The merge step sees facts only.** It never reads raw pages, so it cannot introduce a claim that has no source.
- **Null over guess.** Every prompt tells the model to return null when the information is not present.

## Stage 1: structured records (`structured.py`, no model)

| Source | Facts produced |
|---|---|
| Task | `task` with status and due date. Overdue and upcoming are computed at read time from the due date. |
| Calendar entry | `deadline` with start time and location |
| Activity (non-time types) | `expense` with amount, category, vendor |
| Matter | `case_stage` from the matter stage or status when present |
| Communication | `client_contact` when the client's contact ID is among the senders or receivers |

These facts get `origin = code`, `confidence = high`, and `verified = true`. The quote is the relevant field's text.

## Stage 2: pages (`pages.py`)

For every document source that is a PDF:

1. Open with PyMuPDF. For each page, extract the text layer.
2. A page with fewer than about 50 characters of text is treated as a scan: `has_text_layer = false`.
3. Render every page to a PNG at 150 DPI and save it to `data/pages/`. Scans need the image for extraction, and every page needs it for the source drawer.
4. Store `content_hash` over the page text, or over the image bytes for scans.

Non-PDF documents: extract text for `.docx` and `.txt`; send images straight to the vision path; record anything else as an unsupported source and move on.

## Stage 3: model extraction (`extract.py`)

Runs over PDF pages, notes, and communications. Use the extraction model from config. Run up to 8 calls concurrently. Skip any input whose content hash already has facts.

Input for a page: the page image, plus the text layer when one exists. Input for a note or communication: subject, body, date, author, and participants.

Also pass the list of known provider contacts (ID and name only) so the model can attribute facts to a provider.

Output schema (Pydantic, enforced through structured output):

```
PageExtraction
  document_type: medical_record | bill | lien_notice | insurance | police_report |
                 correspondence | legal_filing | intake | other
  facts: list[ExtractedFact]

ExtractedFact
  kind: one of the fact kinds in docs/architecture.md
  title: short display string, at most 12 words
  event_date: ISO date or null         -- when the thing happened, not when it was written
  amount: number or null
  provider_contact_id: one of the supplied IDs or null
  provider_name_as_written: string or null
  quote: verbatim text from the input that supports this fact, at most 300 characters
  mentions_strategy: bool              -- valuation, negotiation posture, liability opinions
  detail: object                       -- kind-specific, for example body_part and severity
```

One prompt per kind of input: `extract_page.txt` for document pages, `extract_note.txt` for notes and emails, and `extract_record.txt` for the matter's custom-field record. The custom-field record has a prompt of its own so that a change to the note prompt can never re-read the fields behind the money tiles (D42). Court and litigation events are filed as `litigation_event`, dated by the filing, service or decision date the source gives, never by the date a note was written; `status_change` is only a move between stages with `to_stage` set (D41, D42).

Prompt rules, kept in `digest/prompts/` as text files:

- State the document context first: this is one page of a personal-injury case file.
- Define each fact kind in one line.
- Require `quote` to be copied character for character from the input.
- Tell the model to return an empty list for cover sheets, fax headers, and blank pages.
- Tell the model that handwriting it cannot read is null, not a guess.
- No examples drawn from the Sapini matter. If examples are needed, invent a generic one.

## Stage 4: verification (`verify.py`)

Applied to every model-origin fact before it is stored.

1. **Quote check.** For inputs with text, the quote must appear in the input after whitespace normalization. A fact that fails is dropped. For scanned pages, there is no text to match, so the fact is kept at `confidence = medium`.
2. **Second read for money and dates on scans.** For any scan-derived fact with an `amount` or an `event_date` and a kind of `medical_bill`, `lien`, `policy_limit`, `demand`, `offer`, `settlement`, or `deadline`, re-ask the model for only that value from that page. If the two reads agree, set `verified = true` and `confidence = high`. If they differ, keep the fact, set `confidence = low`, and store both values in `value_json`.
3. **Date sanity.** Drop event dates in the future for past-tense kinds, and dates more than 20 years old.
4. **Provider resolution.** If `provider_contact_id` is null but `provider_name_as_written` is set, match it against provider contact names with normalized comparison. Leave null when nothing matches clearly.

## Stage 5: merge (`merge.py`)

Uses the merge model. Each step is one cached call whose input is the stored facts.

1. **Role and field mapping.** Input: relationship descriptions and custom field names with their values. Output: which contacts are medical providers, insurers, opposing parties, or other; and which custom fields map to the canonical slots `case_value`, `coverage`, `policy_limit`, `medical_specials`, `date_of_incident`, `statute_of_limitations`. Stored in `digests` as `field_mapping`. Mapped fields become facts with `origin = code` and the custom field as their source. This is how the product works across firms without field names in code.
2. **Deduplication.** Group facts with the same kind, date, and provider. Keep the one with the best confidence and link the rest as corroborating sources in `value_json`.
3. **Significance.** Score each fact from 0 to 100 using the rubric below. Batch facts in groups of about 50.
4. **Cross-checks.** Compare the sum of `medical_bill` facts with the mapped `medical_specials` field, and extracted policy limits with the mapped `policy_limit` field. Store disagreements so the UI can show both numbers.
5. **Brief.** Input: the top facts by significance, the KPIs, the stage, and open actions. Output schema below.

Significance rubric:

| Score | Meaning | Examples |
|---|---|---|
| 90 to 100 | Changes the value or the outcome | Offers, demands, policy limits, coverage decisions, surgery recommendations, liability findings, limitation deadlines |
| 70 to 89 | Changes the plan | New diagnoses, imaging findings, treatment gaps, lien notices, client decisions, a suit filed or answered |
| 40 to 69 | Routine but relevant | Treatment visits, records received, bills |
| 0 to 39 | Administrative | Scheduling, acknowledgments, cover letters |

Brief schema:

```
Brief
  headline: one sentence, at most 25 words
  stage: intake | treating | treatment_complete | demand | negotiation |
         litigation | settled | closed
  stage_fact_ids: list[int]
  sentences: list[{text: str, fact_ids: list[int]}]     -- 3 or 4 sentences (digest/prompts/brief.txt)
  open_questions: list[str]                             -- things the file does not answer
```

Every sentence must cite at least one fact ID. After generation, drop any sentence whose fact IDs do not exist. If the stage is inferred because Clio has none, the UI labels it as inferred.

## Cost and caching (`llm.py`)

One wrapper function for all model calls. It:

- computes a cache key from model, prompt version, and input content hash, and returns the stored result on a hit;
- records model, tokens, and dollar cost in `llm_calls`, using per-model prices from config;
- retries once on a schema validation failure, then records an error and returns nothing.

`GET /api/ops/cost` reports total tokens and dollars for a full digest of the matter. The submission form asks for the approximate cost to run one case, so this number must be real.

## Run order

`cli digest` runs: structured, pages, extract, verify, merge. Each stage is idempotent and prints counts. A second run with no changes makes zero model calls.
