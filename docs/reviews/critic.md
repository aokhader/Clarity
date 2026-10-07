# Critic reviews

Newest pass first. Findings are ranked by how badly each would hurt in front of a trial attorney. Real values are named by field and tile only, never quoted: this file is committed.

## Pass 2, 2026-10-07 01:54 PDT

This pass used the real matter through the running API (port 8000), with `data/app.db` opened read-only and the committed code from `9c05e39` to `c18388b`. There was no browser. To test the draft checker, I sent invented drafts to `POST /api/matters/{id}/shares/draft-check` for the chiropractic provider's link, first with default settings and then with every setting on. The figures in those drafts were read from `GET /api/matters/{id}` when each test ran; none is written here. No share was created. As a control, I rebuilt the update the app writes itself (`providerUpdateText.ts`) for all ten providers, with default settings and with every setting on, and checked it. All 20 came back `supported`, with no lock and no false flag.

### Findings

1. **Regression: the Case value tile now leads with the recovery cap, and its basis line describes the defendant's policy limit.**
   - Where: Case value tile; `backend/app/services/kpis.py:94-121` (`_case_value`), with `_grouped` at `:63`.
   - Saw: the tile has four values, each from a single record. In order: the recovery-cap note (fact 308); "At least" the valuation (fact 200); "At least" the economic-damages total (fact 515); and the valuation as a point value (fact 55, the Clio field). It also shows "Sources disagree". With one record each, the tie is broken by significance, and fact 308 scores highest, so the first figure is the defendant's per-person limit. At Pass 1, `049da3d` had merged facts 200 and 55, so the valuation led with two records. `ae9f3e7` split them, which was right, but the valuation lost its lead.
   - Expected: the valuation leads. "At least X" and "X" agree, so they should count together when the tile ranks its values. D20's re-extract will take facts 308 and 515 off this tile, but until it runs, demo moment 2 opens on a coverage cap labelled "Case value".
   - Owner: backend (ranking); pipeline and Manager (D20 re-extract and its cost).

2. **The draft checker misses an internal figure written without a currency marker, rounded, or split.**
   - Where: `backend/app/services/text_mentions.py:88-127` (the amount patterns); `services/share_values.py:59-67` (`withheld_values`); the UI line "No amounts or dates to check" (`frontend/src/components/share/DraftCheckView.tsx:18`).
   - Saw: I tested the case value, the defendant's limit and the specials total. The checker locks every exact form:
     - with or without commas, or with cents
     - in quotes or in parentheses
     - "$Xk" within $500 of the figure, and "$X thousand"
     - "X dollars", "USD X", and the figure in words followed by "dollars"
     - two-decimal millions
   - Saw: these pass as `unchecked`. The UI then says there is nothing to check, and Send stays enabled:
     - bare digits, "Xk", "X grand", "X bucks"
     - the figure in words without "dollars"
     - "X USD", "X$", or a full-width dollar sign
   - Saw: these pass as `not_in_file`, and Send stays enabled:
     - the figure rounded to $10k, or a range around it
     - the figure split into two amounts across two sentences
     - thin-space or dot thousands separators
     - "$X grand", which is read as $X
     - three-decimal millions: "$2.125 million" is read as $2
   - Saw: the Firm spend tile's figure passes as `not_in_file`. It is a sum of five internal expenses and is held in no single fact, so it is never a withheld value. A sentence that discloses an internal fact with no figure in it (the settlement plan, a defense exam finding, the client's inconsistent accounts) is `unchecked`, by design (D17).
   - Expected:
     - bare numbers of four or more digits, and "k", "grand", "bucks" and a trailing "USD", read as amounts
     - three decimals parsed correctly
     - computed internal totals among the withheld values
     - a figure within about 10% of a withheld amount flagged (see Needs decision)
     - wording for `unchecked` that does not read as an all-clear, such as "No amounts or dates found. The lock checks figures only."
   - Owner: backend; ui-builder (wording).

3. **False locks on ordinary dates and on $0.**
   - Where: `services/share_values.py:59-92`; `services/draft_check.py:147-155`.
   - Saw:
     - The incident date, in any full form, is locked with "Kept internal: never shared with providers". Every treating provider has the date of injury on its own intake and bills, so "since the accident on <date>" is the first sentence an attorney writes.
     - A month and year ("we expect to hear back in <month year>") is locked whenever some internal fact is dated in that month and the link shows nothing then. 41 of the 43 months in the case's span hold a dated fact.
     - A proposed follow-up day is locked when it falls on an internal calendar entry. That happened for 4 of the 6 days I tried in the next three weeks.
     - "$0" is locked as "about another provider", because another provider has a no-charge line.
   - Expected: the incident date is not locked (see Needs decision). A month written as a month, or a day that only coincides with a task or calendar entry, gets a warning, not the lock. $0 never locks.
   - Owner: backend; Manager for the incident date.

4. **The provider is told that the case last moved more than three years ago.** (`b12930b` changed this; it is still wrong.)
   - Where: the provider page's status tracker, and the generated update's "last movement"; `services/provider_view.py:106-118`.
   - Saw: for every provider, `last_movement_on` is the "File opened" status change, because it is the only dated one. The later stage changes (the renewal and discovery) have no date. The case is in active litigation, yet a provider treating on lien reads that nothing has happened since intake. At Pass 1 the error ran the other way: five days ago, taken from the Clio edit date.
   - Expected: when the latest status change has no date, leave "last movement" out rather than dating it from an older event.
   - Owner: backend.

5. **The "Don't send" lock on a share's note exists only in the browser.**
   - Where: `services/shares.py:116` (create) and `:165-166` (update); `provider_view.py:245`; `ShareComposerForm.tsx:179`.
   - Saw: the composer disables "Create link" while the note is locked. But `POST /api/matters/{id}/shares` and `PATCH /api/shares/{id}` store any note unchecked, and the provider's payload serves it. Changing the settings later never rechecks a stored note. A screener with curl will find this.
   - Expected: the API refuses a note whose check is `do_not_send`, on create and on any update to the note or the settings. Rule 4: the boundary is enforced in the API.
   - Owner: backend. The lead confirms, since it changes what the share routes accept.

6. **Amounts and dates from call notes never reach the draft checker.**
   - Where: `services/known_values.py:15` and `:41-49`, against `CallNotePayload.amounts_cents` and `.dates` (`d6a0330`).
   - Saw: `fact_values` reads only the integer `amount_cents`, `balance_cents`, `low_cents` and `high_cents`, plus a single `on` or `due_at`. A call note keeps its figures in lists, so a figure the firm heard only on a call is neither locked nor supported. It reads "not in the file".
   - Expected: call-note figures are among the withheld values. `call_note` is already internal by default-deny.
   - Owner: backend.

7. **The brief still shows a figure that no fact holds. The fix waits on the re-digest.**
   - Where: the brief's fourth sentence; `GET /api/matters/{id}/brief` (generated Oct 2).
   - Saw: D12 now marks the stale bills total "differs", with today's total and its chips (Pass 1 #1, mitigated). The same sentence has a second figure that no fact holds, marked `not_in_file` and with no source. It equals the economic-damages total minus the specials, so the model computed it. The exam date in sentence three is marked "differs" against the later exam (Pass 1 #3, mitigated). The headline still has no chip of its own (D14), though its one amount is matched to facts. The open question that asks for the incident date (Pass 1 #6) is still there. Three of the eight sentences carry a mark.
   - Expected: after D13, every figure in a sentence is held by a fact that sentence cites.
   - Owner: Manager (D13 go-ahead), pipeline.

8. **The consent wording leaves out the notes model, and a call does not record who confirmed consent.**
   - Where: `frontend/src/lib/callConsent.ts:7-10`; `backend/app/api/calls.py:48-62`; the `Call` model (it has no user column).
   - Saw: the wording read to the other party names Google's speech service only, but the transcript then goes to the configured model provider for notes. It also says "only my side is transcribed", which is not true on a speakerphone. The client sends the firm user with the start request, the server drops it, and the stored consent has no attesting attorney.
   - Expected: wording that names both processors, and the attesting user stored with the call.
   - Owner: ui-builder (wording, with the researcher's brief); backend (the user column).
   - What holds:
     - Consent comes before transcription. `speech.start()` runs only in the start request's `onSuccess`, after the server has stored the consent (`ActiveCall.tsx:88-95`). Resume appears only once a call exists.
     - No transcript reaches a provider. `call_note` is in no share setting, so `released_facts` never selects it. The provider routes are still only the three GETs.
     - Each note renders with its chip, and backend checks the quote's span again before storing it.

9. **The provider's "shared on" and "expires" dates are UTC days.**
   - Where: `provider_view.py:243-244`.
   - Saw: `share.created_at.date()` is taken on a UTC timestamp. A link created after 5 pm Pacific reads as shared tomorrow, and the draft checker's "date this link was shared" follows it.
   - Expected: the firm's local day.
   - Owner: backend.

10. **Minor.**
    - Call notes (`digest/call_notes.py:166-172`): a note's amount is accepted if it lies within the tolerance of either figure. "$1m" carries a $500k tolerance, so a note reading "$1m" passes against a quote of "$600,000". The stored amount is the quote's, but the note text on screen misstates it. Owner: pipeline.
    - The feed still lists one fact twice: the same shoulder-surgery recommendation, from two providers' records. Owner: backend.
    - Process (D23): `0100241` made `billed_cents` nullable in `types.ts` without fixing `ProviderRow.tsx`. The frontend typecheck was red at that commit until `8acfddd`.

### Pass 1, rechecked at HEAD

- **Regressed:** #5 (Case value), now finding 1 above.
- **Fixed on screen:**
  - #2: the basis line reads "The first figure is the sum of 175 bills", and the tile warns only when the server says the sources disagree (`8acfddd`). Fact 201 stays until D20.
  - #7: the header chip is the Clio date-of-incident field.
  - #9: one repeat is left (finding 10).
  - #13: the drawer says "Uploaded". The document's own date needs a re-sync for `received_at`.
  - #15: "No bills on file", from `0100241` and `8acfddd`.
- **Marked on screen; the fix waits on the re-digest (D13):** #1 and #3.
- **Code fixed; the data waits on the re-digest:** #10 (the radiology bill still reads "DEMO"); #16, the stage label's trailing space; #16, the mixed date formats in the brief; and #6, the open question, which is in the brief's input.
- **Still open in code:**
  - #12, now finding 4.
  - #16: the provider's "File opened" date is still two days from the header's opened date.
- **#16 on the coverage limits:** each limit now appears once on the provider page. The client's own policies still read as plain "Policy limit" until D19's re-read.
- **Outside the requested list:**
  - #4 waits on the D19 re-read (no fact has `policy` yet).
  - #8 is partly fixed: each provider shows at most one open request, but "Waiting on others" lists 45 items, 26 of them undated and 11 from the case's first two years.
  - #11 is still missing on disk (page images return 404).
  - #14 is unchanged.

### Rules that never bend

- **Read-only Clio:** `check.sh` passes (8 tests). Calls writes only its own tables. `aeb9819` adds one field to a GET.
- **No case literals:** `check.sh` passes (4 tests). The new prompt (`call_notes.txt`) is generic. A scan of the trial's diff for names, phone numbers and statute references found none.
- **Every fact sourced:** each call note has a call source, a quote and offsets. The gaps are the brief's computed figure and the headline's missing chip (finding 7).
- **Provider boundary:** no provider route exposes draft-check: `POST /api/p/{token}/draft-check` returns 404, and the OpenAPI lists three provider GETs. D17's fact refs appear only on the two firm routes. The share note is the exception (finding 5).
- **No model on page load:** holds. The only model call is the notes thread, which `POST /calls/{id}/end` starts. No GET reaches `llm`.

### check.sh

At `d6a0330`, with backend's uncommitted files in the tree: lint ok, Clio read-only ok (8), no case data ok (4), nothing private ok (4), backend tests ok (246), frontend types ok, other Node tests SKIPPED (none found). No step failed, so there was nothing to attribute to uncommitted work.

### Needs decision (for the lead)

1. **The incident date on a provider's link.** Should a draft that states it count as supported for every provider, without adding it to the payload? Recommendation: yes. Providers already have it, and locking it is the first false lock an attorney meets.
2. **Figures near an internal amount.** Options: (a) lock any amount within 10% of a withheld amount; (b) flag it "close to an internal figure" without locking. Recommendation: (b), plus reading unmarked numbers of four or more digits as amounts.
3. **Dates that only coincide.** Should task and calendar dates, and month-only mentions, lock a sentence, or only warn? Recommendation: lock the dates of deadlines, demands and offers; warn for the rest.
4. **Finding 5** changes what the share routes accept (a 422 for a locked note), so it needs the lead's yes before backend starts.

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
