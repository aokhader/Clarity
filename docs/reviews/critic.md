# Critic reviews

Newest pass first. Findings are ranked by how badly each would hurt in front of a trial attorney. Real values are named by field and tile only, never quoted: this file is committed.

## Pass 1, 2026-10-07 00:52 PDT

Run on the real matter through the running API (port 8000), with `data/app.db` opened read-only and the code at `9c05e39`. No browser. Every firm endpoint answered in 0.2 to 0.35 s, with no model configured, so rule 5 holds. Traced by hand: the four KPI tiles, the provider bill totals of the chiropractic, surgical-facility and radiology providers, every amount and date in the brief, and the header's incident date.

### Findings

1. **The brief states a medical-bills total that no cited fact contains and that contradicts the specials tile.**
   - Where: Brief, fourth sentence; `backend/app/digest/merge.py:192` and `:220`.
   - Saw: the sentence's bills figure is the pre-fix total. It cites six facts (a task, three policy-limit or value facts, an offer, a matter field), and none of them states that figure. It differs from the bill sum on the Medical specials tile. The cause is structural: `key_figures` hands the brief model computed totals with no fact ids, so even a fresh brief can state a bills figure whose chips lead elsewhere.
   - Expected: every figure in a sentence appears in a fact the sentence cites, or the sentence carries the bill-sum facts (D12's read-time check covers the stale case; this covers the next brief too).
   - Owner: pipeline (brief input), backend (B4, D12), Manager (re-digest, D13).

2. **The Medical specials tile says "Sources disagree" and "Matches the sum of 175 bills" at once.**
   - Where: Medical specials tile; `backend/app/services/kpis.py:144-150` with `frontend/src/components/firm/KpiTile.tsx:70-76`.
   - Saw: two values. The bill sum, corroborated by six firm statements, and a second figure from fact 201, which is the case-evaluation note's economic-damages total (specials plus claimed wage loss) filed as `medical_specials`. Since `049da3d` the basis reads "Matches", while the tile still prints the disagreement warning because there are two values.
   - Expected: one figure. Economic damages are not medical specials, and the tile must not contradict itself.
   - Owner: pipeline (the kind of fact 201; the extraction prompt should separate economic damages from specials), backend (basis wording when a matching figure leads).

3. **The brief merges two defense exams into one, dated the earlier.**
   - Where: Brief, third sentence ("An IME dated ...").
   - Saw: the sentence cites facts from two different documents. The neurology exam and the orthopedic exam, which a different doctor performed weeks later. The finding that complaints did not match objective findings comes from the later exam (fact 1924, document page 11), but the sentence dates it to the earlier one.
   - Expected: each exam named with its own date. `_brief_row` (`merge.py:275`) sends no source title or type, so the model cannot tell the two documents apart.
   - Owner: pipeline (brief rows carry the source title and date); backend (the D12 checker should also compare the sentence's dates with its cited facts' dates).

4. **The Coverage limit tile shows three different policies as "Sources disagree".**
   - Where: Coverage limit tile; `kpis.py:101`; `schemas.py:117` (`PolicyLimitPayload`).
   - Saw: per-person values from the defendant's liability policy, the client's no-fault basic economic loss limit, and the client's UM/UIM limit, flagged as a disagreement under "Per person". No-fault is not liability coverage. The payload has no field for whose policy it is, so code cannot separate them.
   - Expected: the defendant's liability limit as the tile's figure, with the client's own policies labelled or left out.
   - Owner: pipeline and backend (contract field); see Needs decision.

5. **The Case value tile lists a recovery cap and an economic-damages total as valuations.**
   - Where: Case value tile; facts 308 (a note's "recovery is capped at the limit") and 515 (a matter field's economics total), both of kind `case_value`.
   - Saw: three values and "Sources disagree". Only the valuation (fact 200, which matches the Clio field) is a case value. The basis line now quotes fact 200's basis, which states the economics figure.
   - Expected: one value. A coverage cap and an economic-damages total are not valuations.
   - Owner: pipeline (kind classification).

6. **"Not answered by the file" asks for the incident date, which the header shows with a source.**
   - Where: Brief, second open question; header incident date.
   - Saw: the header gives the incident date (203 incident facts and the Clio date-of-incident field all agree), while the brief's amber box says the file does not answer it.
   - Expected: no open question that the page answers elsewhere.
   - Owner: pipeline (brief input or prompt), applied at the re-digest.

7. **The header's incident date opens a quote that does not contain the date.**
   - Where: Header, incident date; `backend/app/services/matter_queries.py:105-111` (`_best`), `:164`.
   - Saw: `_best` breaks the tie between 198 same-day incident facts by significance and picks fact 765, page 3 of the defendant's discovery response. Its quote describes the impact with no date, and its title names a different location from the matter description. Fact 54, the Clio date-of-incident field, quotes the date itself.
   - Expected: the chip opens a source that shows the date: the Clio field, or a fact whose quote contains it.
   - Owner: backend.

8. **Requests never close, so a provider is told it still owes records it sent years ago.**
   - Where: Provider page, Requests; firm Providers panel; action board; `backend/app/services/providers.py:20-35`, `provider_view.py:164`.
   - Saw: the chiropractic provider shows 8 open requests, on the panel and in its share preview. One is the complete-file request from the case's first months, which the firm's own note records as received months later. Four more are undated restatements of the same ledger request. "Waiting on others" lists 65 items, most from the case's first year. Every `record_request` keeps the status it had when it was written.
   - Expected: one open item per outstanding request, closed by a later records-received fact. Demo moment 4 shows this list to the provider.
   - Owner: pipeline (status reconciliation and dedup), backend (`distinct_requests`).

9. **"The ten that matter" shows one fact three times.**
   - Where: Ranked feed (`/feed`).
   - Saw: three rows restate that the client gave inconsistent accounts, and two restate the defendant's per-person limit, so 5 of the 10 slots are repeats. The last digest's merge reported `deduplicated: 0`.
   - Expected: each fact once, citing every record that states it, as the injuries list now does (`336c8c6`).
   - Owner: pipeline (merge dedup), or backend (group in `matter_feed`).

10. **The radiology provider's only shared bill reads like placeholder data.**
    - Where: Provider page, Bills (radiology provider); `backend/app/digest/mapping.py:514` (`_ledger_fact` title).
    - Saw: the ledger is the counted record for this provider, so its one bill shows the Clio activity's raw description, which contains the word "demo" twice, with no source the provider can open. A screener will read it as hardcoded.
    - Expected: a neutral label such as "Charges on the firm's ledger", with the service dates.
    - Owner: pipeline (ledger fact title) or backend (provider label).

11. **One pleading cannot be shown: its PDF and all 27 page images are missing on disk.**
    - Where: Source drawer for 65 facts, including the chip on the brief's statute-of-limitations sentence (fact 586, page 3).
    - Saw: sync run 3 recorded a download error for this document, and digest run 7 counted it as `file_missing`. The page images return 404. `feff0c0` now says "could not be loaded" in place of a broken image, but demo moment 1 cannot show this scan.
    - Expected: the scan. `21fa27b` (P2) makes the next sync retry it.
    - Owner: Manager (sync go-ahead), pipeline.

12. **The provider page's "last movement" date is the day the Clio record was last edited.**
    - Where: Provider page, status tracker; `mapping.py:359` (the stage fact's date is the matter's `updated_at`); `provider_view.py:106`.
    - Saw: "last movement" is the day the matter was loaded into Clio, five days ago, and no case event happened that day.
    - Expected: the date of the latest dated status change or case event, or no date.
    - Owner: backend.

13. **The source drawer dates every document by its upload day.**
    - Where: Source drawer header; `backend/app/services/source_views.py:221`; `frontend/src/components/firm/SourceBody.tsx:18`.
    - Saw: an itemized bill from years earlier reads "Document · " followed by the upload day.
    - Expected: the document's own date, or the label "Uploaded".
    - Owner: backend, ui-builder.

14. **The Injuries panel leads with the defense's negative findings.**
    - Where: Injuries panel.
    - Saw: 194 groups. The six shown first are IME and expert-review findings: resolved, MRI normal, no recent traumatic injury. The client's own injuries come later.
    - Expected: the client's injuries first, with defense findings marked as such or kept in the feed.
    - Owner: backend (order) or ui-builder.

15. **"Not found" is shown as zero on the Providers panel.**
    - Where: Providers panel; `backend/app/schemas.py` (`ProviderOut.billed_cents: int`); `providers.py:100`; `frontend/src/components/share/ProviderRow.tsx:37`.
    - Saw: the treating surgeon, whose charges the surgical facility bills, reads "Billed $0". No bill names him; nothing in the file says he billed zero.
    - Expected: "No bills on file". Backend already asks in STATUS whether to make `billed_cents` nullable; yes.
    - Owner: backend (contract), ui-builder.

16. **Minor items.**
    - The provider's "File opened" update (from a note) and the header's opened date (from Clio) are two days apart. Owner: backend.
    - With coverage limits switched on, the provider sees the same limit up to three times, plus the client's own UM/UIM limit labelled "Policy limit per person". Owner: backend (`provider_view.py:143`).
    - The brief mixes MM/DD/YYYY and ISO dates in one paragraph. Owner: pipeline (prompt).
    - The stage label is built as "Stage: " plus Clio's label, which keeps Clio's trailing space. Owner: pipeline (`mapping.py`).

### Rules that never bend

- **Read-only Clio:** `check.sh` passes (8 tests). The share preview is a POST to our own API that writes nothing: `GET /shares` was still empty after 23 previews.
- **No case literals:** `check.sh` passes (4 tests). A scan of the trial's diffs for names and figures from the matter found none.
- **Every fact sourced:** every fact in the database has a quote, and every document fact has a page. The gaps are the brief's uncited figures (finding 1) and the headline with no chip (known; D14 applies it at the re-digest).
- **Provider boundary:** I previewed all ten providers with all seven settings on, and no internal or strategy-flagged fact reached any payload. Preview and link share `provider_payload`, so they cannot drift. The preview lacks only `onOpenSource`, so its chips do not open.
- **No model on page load:** holds. The health endpoint reports no model configured, and every page still loads.

### The trial's commits (`987c1bf..9c05e39`)

- `049da3d` (KPI): it introduced finding 2. It also turns a one-ended valuation ("at least X", low end only) into the point value X (`kpis.py:84`), and it drops per-occurrence limits from the Coverage tile. Both changes are silent.
- `0f0bbf8` (P1) and `23e23dc` (D7): they bump the extraction and significance prompt versions. Extraction, however, skips pages already extracted (`extract.py:180`) and records whose hash matches (`records.py:80`), and scoring touches only unscored facts (`merge.py:137`). So the re-digest in D13 will not apply either prompt to existing facts; it reruns only the mapping and the brief. P1's defect never reached this data: no fact stores a bill balance, and the stored case-value high ends are correct.
- `21fa27b` (P2): a run with any per-item error is never a baseline again, so a document that always fails makes every later sync a full pull. This is minor.
- `1cd54d0` (P4): if the role call fails on a first digest, with no previous mapping, party facts are rebuilt from empty roles. This is minor.
- `daff938`, `b988547`, `9c05e39`, `83ad882`, `336c8c6`, `feff0c0`: nothing breaks a rule.

### check.sh

At `1cd54d0`: lint ok, Clio read-only ok (8), no case data ok (4), nothing private ok (4), backend tests ok (122), frontend types ok, other Node tests SKIPPED (none found). No step failed.

### Needs decision (for the lead)

1. **What the D13 re-digest actually changes.** As the code stands, it rewrites the mapping and the brief only. It does not re-extract or re-score. That is cheap, but it does not fix the misfiled facts behind findings 2 and 5 (facts 201, 308 and 515). Options:
   - (a) Re-extract just their two source records by clearing their processed hash: two extraction calls.
   - (b) Accept the misfiling and have the tiles ignore it.
   - (c) Re-extract everything, at roughly the cost already recorded for this matter.
2. **Coverage tile (finding 4).** Options:
   - (a) Add a policy-holder field to `PolicyLimitPayload` (a contract change, then a re-extract of the limit facts).
   - (b) Show one line per stated policy, labelled by its source, and drop the "Sources disagree" warning on this tile.
3. **Extend D12 to dates as well as amounts.** This would have caught finding 3 (the cited facts carry two different exam dates), and it could catch finding 6 if an open question that some fact answers were dropped.
