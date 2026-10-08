# Critic reviews

Newest pass first. Findings are ranked by how badly each would hurt in front of a trial attorney. Real values are named by field and tile only, never quoted: this file is committed.

## Pass 4 (D38 Overview), 2026-10-08 14:39 PDT

C4, on the real matter after the D38 Overview pass. I used the running API on port 8000 and read the code at `e61aee2`. `692af64` to `4cb81ba` landed during the pass and touch only tests, fixtures and docs, so the traced path did not change. There was no browser. I read what each block renders from `OverviewView.tsx` and its components, and called the routes those components call. `data/app.db` was opened read-only. I sent only GETs: no visit recorded, no share, no model call.

Traced by hand:
- the identity header's two chips;
- What happened:
  - the incident account and all 179 facts behind it (8 opened in the source view);
  - the three injury rows;
  - the liability row;
- the Now strip's next step, statute, last client contact and counts, including all 44 items behind "waiting on others";
- all 10 rows of the story so far, with the candidates the selection passed over;
- the headline, 5 sentences and 13 of their facts;
- the money row against the brief's figures.

### Findings

1. **The Statute cell says the statute passed, in red, but its own chip opens a record that says it was met.**
   - Where: the Now strip, first screen.
     - `frontend/src/components/firm/NowStrip.tsx:60-64` turns any past date red with "passed N days ago".
     - `frontend/src/lib/facts.ts:76-83` (`statuteDeadline`).
     - The cause: `backend/app/digest/structured.py:95-103` builds the statute deadline fact without the Clio task's status.
   - Saw:
     - The cell shows the date of fact 2, red, as passed months ago.
     - Fact 2's chip opens the Clio task it came from (source 158). The task's text says the limitation period was satisfied, since the notice was served and suit started in time, and that the entry is kept for the record.
     - In Clio that task is `complete`, with `completed_at` set. The task fact built from the same source (fact 1) has `status: complete`, but the deadline fact (fact 2) has no status at all.
     - The stage is Litigation, and the brief's third open question says a limitations defense is pleaded. A trial attorney reading red "passed" next to a pleaded limitations defense will think the firm missed the statute: the worst alarm the page can raise, and the source says it is false.
   - Expected: a met statute reads "Met", in neutral or green, with its date and the same chip, and is never red.
   - Recommendation (Needs decision 1): code only, no model call, fix now.
     - backend: give `DeadlinePayload` an additive `status`. Fill it when the fact is served, from the sibling task fact of the same source, so no re-digest is needed.
     - pipeline: later, set the status in `structured.py` as well.
     - ui-builder: the wording.
     - lead: `docs/ui.md` says "red once passed" and needs the exception for a met statute.
   - Owner: backend, then ui-builder.

2. **"All 192 injuries" is wrong by an order of magnitude.**
   - Where: What happened, under the Injuries label (`WhatHappened.tsx:61-69`), first screen. For Attorney's Injuries panel shows the same count (`InjuriesList.tsx:22`).
   - Saw:
     - `groupSameInjuries` (`lib/facts.ts:110-122`) groups 319 injury and diagnosis facts by exact kind, title, body part and severity, which gives 192 groups.
     - The groups include one complaint line per chart visit, worded a little differently each time.
     - They also include defense-exam and expert-review findings that there is no injury, or that it has resolved, each counted as an injury.
     - The brief's own injury sentence names four body regions.
   - Expected: no count, or a count of something real. Either "All injuries and diagnoses" with no number, or a count by body region.
   - Owner: ui-builder (wording now); backend, if a per-region count is wanted.

3. **The Incident line shows one side's account, cited as 179 sources, on the one point the file says is in dispute.**
   - Where: What happened, the Incident line (`header.incident_account`, `services/incident.py`), and row 1 of the story so far. The margin reads "+177 more" (`BriefCitations.tsx`, `SourceChipList.tsx`).
   - Saw:
     - The account is the history line of the treatment charts: the client's own description of the collision, printed on every visit page. I opened 8 of the 179 facts (1585, 1467, 1403, 816, 1282, 868, 1581, 1130), and each quote is on its page. The 179 come from only 9 records, and all 179 give one account, so the group does not mix accounts.
     - But "+177 more" counts pages, not records. It reads as 179 independent sources for the client's version, when it is one statement copied onto every visit page of 9 records.
     - The file disputes that version:
       - fact 320, significance 97, from a firm note: the client gave inconsistent accounts of the collision;
       - fact 318: liability is contested on the mechanism;
       - fact 765, from the defense driver's report produced in discovery: the opposite account.
     - The Liability row below shows fact 292, significance 96. It holds its text, but it states the scope-of-employment issue and not that the mechanism is contested. That is in fact 318, significance 95, from a newer note.
     - On the first screen, only the headline's "liability contested" qualifies the line. The inconsistency is in sentence 4 of Where it stands, below the fold.
   - Expected:
     - The margin counts records: "+8 more records", one chip per record.
     - The first screen shows that the incident is contested on liability whenever a liability fact says so.
   - Owner: backend (fold `restated_by` to one per record, or add a record count); ui-builder (the "+N more" wording). The liability rule is Needs decision 5.

4. **The stage track says treatment is complete. The client is still treating.**
   - Where: `StageTrack.tsx:31-35` marks every step before the current one `completed`, with a check mark and ", completed" for screen readers. First screen.
   - Saw:
     - At Litigation (step 5), "Treating" shows a check mark.
     - The file says otherwise:
       - the action board's upcoming items include treatment appointments this week and next (deadline facts 30, 31 and 32);
       - the latest client contact (fact 52) is about continuing therapy;
       - a firm note says treatment is open (fact 292's record);
       - a second surgery is recommended and not scheduled (fact 1427).
     - The README counts "whether the client is still treating" among the 10 first-screen answers. The only first-screen signal for it is this check mark, and it gives the wrong answer.
   - Expected: earlier steps read "passed", not "completed", or Treating stays open while treatment is ongoing.
   - Owner: ui-builder; backend, if a "still treating" signal is wanted (for example, the next treatment appointment).

5. **The story so far lists scheduled events as events that happened.**
   - Where: `services/matter_queries.py:40-50`. `KEY_EVENT_KINDS` includes `DEADLINE`, and `_has_happened` (`:340`) treats a past deadline as an event.
   - Saw: 3 of the 10 rows are past deadlines.
     - Row 2 (fact 1398, a surgery scheduled, from a pre-operative note) and row 3 (fact 1518, the same surgery performed) fall on the same day, so one event is told twice.
     - Row 7 (fact 772) is a subpoena's appearance date for a deposition, listed as an event on that day. A firm note written months later (fact 299) says that deposition is still outstanding. The story tells the attorney a deposition happened that did not.
     - Row 6 (fact 590) says "noticed for" in its title, so it is honest.
   - Expected: past deadlines leave the story. The rows go to the next candidates: records received (fact 479, significance 90), coverage (fact 402, 88), and so on.
   - Owner: backend, code only, with a test that a scheduled day and a performed event on one day give one row.

6. **The story so far never says a suit was filed.**
   - Where: the same selection, together with the kinds the facts were given.
   - Saw:
     - The stage is Litigation, and open question 3 turns on a renewed action. Yet no row covers:
       - the first suit (fact 566, dated, kind `other`);
       - its dismissal and the renewal (fact 550, a `status_change` with no date; fact 572, dated, `other`);
       - the answer (fact 580, dated, `other`);
       - the opening offer (fact 1986, an `offer` with no date).
     - The only status change with a date is the file opening, at significance 20.
     - The story goes from the demand to a deposition notice, with nothing to explain why there is a deposition.
   - Expected: filings, dismissals, renewals and answers as dated status changes.
   - Owner: pipeline. It needs a prompt line and a re-read of the pleading records, so a cost and the Manager's go-ahead (Needs decision 3). Otherwise, a README known issue.

7. **"44 waiting on others" includes about 22 demands made of the client, which the firm owes.**
   - Where: the Now strip's To do cell (`NowStrip.tsx:74-82`), first screen; `actions.waiting_on_others`.
   - Saw:
     - 42 of the 44 are `record_request` facts, and `RecordRequestPayload` has no direction (`schemas.py:106`).
     - By my count, 22 are defense or carrier demands for the client's records, authorizations and disclosures. The rest are the firm's requests to providers, the client and the defense.
     - Several are restatements of each other.
     - Pass 2 #8 raised the list's size (45 then). It now sits on the first screen as a number.
   - Expected:
     - now: the count reads "44 open requests" (ui-builder);
     - later: a direction on each request, inbound or outbound (pipeline, a re-read; Needs decision 4).
   - Owner: ui-builder, then pipeline.

8. **Two different "Next step"s on one page.**
   - Where: the Now strip's Next step (`lib/facts.ts:89-96`) and Where it stands, sentence 5.
   - Saw:
     - The strip shows the oldest overdue task, fact 3, weeks overdue.
     - The brief's last sentence begins "Next step:" and cites a different task, fact 8, due in two days.
     - Both tasks are about getting the same surgery date from the same office. Each is right on its own terms, but the page names two next steps with two due dates.
   - Expected: when the strip picks an overdue item, its label reads "Overdue" (or "Most overdue"), so it does not compete with the brief's "Next step".
   - Owner: ui-builder.

9. **The three injuries do not match the brief's injury sentence.**
   - Where: What happened, the Injuries rows (`WhatHappened.tsx:31`, the first 3 groups).
   - Saw:
     - The brief names four regions. The three rows show:
       - a head-imaging finding (fact 1478);
       - a shoulder complaint line from a chiropractic visit (fact 1163), rather than the diagnosis itself (fact 1402 is fifth);
       - a spine finding (fact 1485), which the brief does not name.
     - Not shown:
       - the knees, which have treating-provider diagnoses (facts 1357 and 1353);
       - the other shoulder, the one with the pending surgery.
     - All three quotes are on their pages.
   - Expected: one row per body region, with a diagnosis preferred over a complaint line.
   - Owner: ui-builder, or backend if the server should pick.

10. **Minor.**
    - Rows 8 and 9 of the story (facts 1859 and 1861) are two diagnoses from one page of one defense-exam report: one exam, two rows. Rows 8 to 10 are defense exams, but the lane says Treatment (`lib/labels.ts:92`, where `diagnosis` maps to treatment).
    - Those rows are dated by each report's own date of examination. A firm note (fact 221's record) and the calendar (deadline facts 21 and 22) put both exams about six months later. The file contradicts itself, and the chips support what is shown. Worth knowing before the demo.
    - The Incident line's "+177 more" is a count, not a button (past 8 sources), so 8 of the 9 records behind the account cannot be opened from the Overview. The drawer lists no corroborating tabs for it.
    - Pass 3 #2 (the other driver's policy labelled as the client's) is still in the Coverage disclosure. It is behind "more" now, off the first screen.

### Verified correct

- **Identity header.**
  - The incident chip (fact 1930) opens the matter record, whose date-of-incident field holds the date shown.
  - The stage chip (fact 1929) opens the same record, whose stage field reads Litigation.
  - The stage, the headline's opening word and the brief's stage facts (1929, 215) agree.
- **Incident account.**
  - It is a model fact, never the Clio field (D39).
  - All 179 facts are one account, from 9 records, on the header's incident day.
  - Story row 1 is the same fact (1585), so What happened and the story agree.
- **Injuries and liability:** the chips of 1478, 1163, 1485 and 292 each open a page or note that holds the text.
- **Now strip.**
  - Next step: fact 3 is the oldest of 4 overdue tasks, and Clio has it pending.
  - Last client contact: fact 52 is the latest dated client contact, and its call note holds it.
  - To do: the counts are 4, 7 and 44, as the actions route returns them.
- **Story so far.**
  - All 10 quotes are on their pages or notes.
  - The rows run oldest first.
  - The demand's two records fold into one row (388, restated by 182).
  - Nothing is dated after today.
- **Bottom line and Where it stands.**
  - I spot-checked 13 cited facts (1929, 1964, 318, 1968, 1957, 1958, 1959, 1931, 1932, 1952, 286, 320, 323), and each opens a source that holds it.
  - D12 marks: the headline and sentences 1, 3 and 5 are `supported`, and sentences 2 and 4 are `unchecked` (no figures).
- **Money row:**
  - the Case value lead, the Coverage lead and the Medical specials figure equal the brief's three figures;
  - no figure on the page disagrees with another;
  - the Coverage tile has no false warning (D37 holds).
- **Since you last opened** is keyed to the Clio record's created or updated time (`services/visits.py:43`), so the 93 facts rebuilt by the 2026-10-08 runs do not show as news.
- **`check.sh` at `692af64`:** lint ok, Clio read-only (8 passed), no case data (4), nothing private (4), backend tests (419 passed), frontend types ok. Other Node tests SKIPPED (none). No step failed.

### Rules that never bend

- Read-only Clio, no case literals and nothing private: all pass in `check.sh`.
- Every fact sourced: every chip I opened holds its text. The open questions still state premises without chips (Pass 3 #6).
- No model on page load: every Overview route is a GET over stored facts, and the last digest run did not move.

### Needs decision (for the lead)

1. **A met statute** (#1): `status` on the deadline payload, filled when served from the task fact of the same source. The cell then reads "Met" in neutral, and `docs/ui.md` gets the exception. Recommendation: now, code only.
2. **Past deadlines in the story** (#5): drop them from `KEY_EVENT_KINDS`. Recommendation: now, code only.
3. **The litigation in the story** (#6): either a pipeline prompt line plus a re-read of the pleading records (cents at D36 rates; the Manager's go-ahead), or a README known issue. Recommendation: the known issue now, and the re-read with any later run.
4. **Request direction** (#7): relabel the count now. Add an inbound/outbound field later, with the same re-read as (3).
5. **Liability on the first screen** (#3): show up to two liability rows when the next one is within a few points and from a newer record, or always prefer the newest of near-equal facts. Recommendation: two rows. Either way, count restatements per record.

## Pass 3, 2026-10-08 04:10 PDT

This pass checks the real matter after the D36 model runs: (a), the re-digest, and (b), the re-read of 9 records under P13. I used the running API on port 8000 with no browser, the code at `f49469a`, and `data/app.db` opened read-only. The state before the runs comes from `app.db.bak-20261008T104916Z` (before (a)) and `-105033Z` (before (b)), both opened read-only and immutable. I made no model calls, created no share and wrote nothing. For the draft checker and the provider view, I used `POST .../shares/draft-check` and `POST .../shares/preview`, which build a share in memory and never save it.

Traced by hand:
- every sentence of the brief, its headline, and the 15 distinct facts they cite;
- the 9 rows of the Coverage tile and their 25 facts;
- the Case value and Medical specials tiles;
- the bill totals of all ten providers;
- each of the 9 re-read records, fact by fact, against its state before the runs.

### Findings

1. **The Coverage tile warns "Sources disagree" when no record disagrees. The warning makes the tile list all nine figures as equals, so the defendant's limit no longer leads (D19).**
   - Where: Coverage tile. `backend/app/services/kpis.py:167-225`: `_conflict` and `_may_match` treat a missing policy or basis as "could be any". `frontend/src/components/firm/KpiTile.tsx:34` drops the lead figure whenever `sources_disagree` is true.
   - Saw: two facts set the flag.
     - **Fact 1985** (record 62, the note of the adjuster's response) is tagged as the defendant's policy with no per-person or per-occurrence basis. The note refers once to the defendant's limit, with no basis, while describing the opening offer. Its figure equals the defendant's per-person figure, which five other facts state (1952, 1993, 2003, 2015, 2019). It differs from the per-occurrence figure, so the rule calls it a conflict. **Verdict: a restatement of the tagged per-person figure, not a disagreement.**
     - **Fact 2012** (record 109, the carrier's email saying the client's no-fault benefits are exhausted) has no policy tag. Fact 2011, from the same record, names the coverage as no-fault. The figure equals the client's no-fault limit, which three facts state (1956, 1981, 2007). With no policy tag it "could be" any limit, so it conflicts with every other figure. **Verdict: a restatement of the tagged no-fault figure that the model failed to tag, not a disagreement.**
     - Neither case is unclear. In the whole store, every per-person and per-occurrence statement of the defendant's limit agrees: five facts state the per-person figure and four the per-occurrence figure.
   - Expected: no warning. The tile should lead with the defendant's per-person limit and list the rest under it, labelled.
   - Recommendation: **option (1), fix now, code only, no model call.**
     - A limit with no policy or no basis counts as another source for a tagged row when its amount equals that row's figure and the row is one it could be. Fold it into that row: 1985 joins the defendant's per-person row, and 2012 joins the client no-fault row.
     - If the figure equals more than one candidate row, keep it as its own unlabelled row, with no warning.
     - Flag a conflict only when the figure equals none of the rows it could be.
     - Also take (2): when a real conflict exists, the defendant's per-person figure still leads, and the warning attaches to the rows in conflict. A single stray figure should not flatten the whole tile.
     - With (1) applied, the tile has 7 rows and leads with the defendant's limit.
     - Pipeline note only: the P13 prompt should tag a basic-economic-loss figure as client no-fault. No re-read is needed once (1) lands.
   - Owner: backend, with a test on both shapes. The README already lists this under Known issues.

2. **The defense driver's personal auto policy is labelled "Client's other policy".**
   - Where: Coverage tile, the rows "Client's other policy, per person" and "per occurrence". The facts are 1975 and 1976, from record 48, the firm's coverage note on the defense side. `PolicyLimitPayload.policy` (D21) has four values: `defendant_liability`, `client_no_fault`, `client_um_uim` and `client_other`.
   - Saw: the enum has no value for another party's liability policy, so the model chose the nearest one. An attorney reading the tile learns that the client holds a second policy at the same figures as the defendant's. That is false. The same record says this policy is where recovery would come from if the employer leaves the case on scope of employment (fact 1977, a recovery cap; fact 2010, a possible second defendant). The label hides a second source of recovery and invents a client policy.
   - Expected: a label such as "Other liability policy (another party)", listed after the defendant's own limit.
   - Recommendation: Needs decision 2. In the meantime, add a README known issue. The README's "tagged by policy, all but one" should say that two more are tagged wrongly (reviewer).
   - Owner: backend (an additive enum value in `schemas.py` and `types.ts`, and its label in `kpis.py:33`); pipeline (one line in the prompt, then a re-read of record 48).
   - Cost: one extraction call. The changed facts also change the brief's input, so the brief is rewritten too: a few cents at D36 rates.

3. **Demo moment 1: none of the brief's visible chips opens a scanned page.**
   - Where: `frontend/src/components/firm/BriefCitations.tsx:6` (`CHIPS_PER_SENTENCE = 2`). Chips are drawn in the order the model listed the facts.
   - Saw: the 15 distinct facts that the brief and headline cite break down as:
     - 9 from the Clio matter record itself: its custom fields and summary (1929, 1931, 1932, 1952, 1957, 1958, 1959, 1964, 1968);
     - 4 notes (286, 318, 320, 323);
     - 1 task (8);
     - 1 document page (1518).
   - Saw: 1518 is the fourth chip on sentence 1, so it sits behind "+2 more". The first chips of the headline and of every sentence open the matter record, a note or the task.
   - Saw: every quote is found in its source view, and 1518's page image serves.
   - Saw: the October 2 brief led its exam sentence with document chips. The new brief is drawn mostly from the firm's own Clio fields, and a screener may read it as a restatement of the Clio summary.
   - Expected: on screen, the brief's first chip opens a scanned page wherever the sentence cites one.
   - Recommendation: fix now (ui-builder). In `BriefCitations`, the one place that sets the citation design, draw document-page chips first. In the meantime, the demo script opens "+2 more" on sentence 1.

4. **Demo moment 3: the draft checker says the date of the accident is "not in the file".**
   - Where: `backend/app/services/draft_check.py:153-182`. The panel's wording is in `frontend/src/components/share/DraftCheckView.tsx:16`.
   - Saw: in a draft for the chiropractic provider's link, the incident date returns `not_in_file`, "Not found in the file", in all four forms I tried: ISO, the full month name, the short month name, and numeric. The panel then says "Some amounts or dates are not in the file". Yet the header shows the date with a chip (fact 1930), and more than 200 incident facts carry it.
   - Saw: under D25, a date that matches only a withheld fact of a kind that is not sensitive does not lock, which is right. But it then falls through to "Not found in the file". The same happens to any internal date that is not sensitive, such as a treatment date when treatment activity is off.
   - Saw: Pass 2 #3, the false lock, is fixed. This false "not in the file" replaced it. The model runs did not cause it.
   - Expected: either a wording for "in the file, not on this link", or the incident date counted as supported (Pass 2, Needs decision 1).
   - Owner: backend, with ui-builder for the wording. Fix now if the demo types a date; otherwise add a README note.
   - Minor, same panel: the lien figure locks (correct), but the reason reads "about another provider", and no lien fact has a provider.

5. **A hidden item on a share comes back after a re-digest that rebuilds its fact.**
   - Where: `Share.hidden_fact_ids_json` (`models.py:294`), read in `services/visibility.py:118` and `services/share_values.py:75`.
   - Saw: hidden items are stored by fact id, but a re-digest that rebuilds a record's facts gives them new ids. The two runs replaced 91 facts this way:
     - run (a): 43 facts, those of record 1, the five expense activities and the nine bill activities (sources 189 to 202);
     - run (b): 48 facts, those of the 8 other re-read records.
   - Saw: every bill came back with the same source, provider and amount (204 bill and lien facts before, 204 after). Any share that hid one of those bills would now show it. No share exists on the real matter, so nothing leaked. This is a rule 4 gap that a screener reading `visibility.py` could find, and it is not in Known issues.
   - Expected: a hidden item stays hidden after a re-digest. Either key it by something stable (source, kind, page and quote), or carry the hidden ids over when a fact is replaced.
   - Recommendation: add a README known issue now; the fix comes after the freeze.
   - Owner: backend.

6. **The brief is right but thin. It drops the risks a trial attorney asks about first.**
   - Where: `GET /api/matters/{id}/brief`; `backend/app/digest/prompts/brief.txt` v4 asks for "3 or 4 sentences, each at most 20 words".
   - Saw: every amount and date checks out.
     - The three amounts in sentence 3 each match a fact the sentence cites (1931; 1952 and 1964; 1932).
     - The bills figure equals the specials tile's bill sum, so the stale figure from Pass 1 #1 is gone.
     - The surgery date matches fact 1518's own date, and the due date matches task 8's due date to the day.
     - D12 gives 3 sentences "supported" and 2 "unchecked" (no figures); the headline is "supported" through fact 1964.
     - Each open question is unanswered in the store.
   - Saw: compared with the October 2 brief, it no longer says:
     - what the defense medical exams found. Facts 1859, 1861, 1864, 1923, 1924 and 1927 are still stored, with significance 93 to 95;
     - that a limitations defense is pleaded (586, 233). It appears only inside open question 3, whose premise has no chip;
     - that an opening offer was made (1986);
     - that the wage claim is weak. It appears only as open question 4;
     - that the lien comes off any recovery (1965, 1995, 2009).
   - Saw: the headline states the recovery cap without the condition that records 48 and 84 attach to it: unless a second defendant is reached (1977, 2008, 2010).
   - Saw: the injuries sentence comes from the Clio summary and says only "a head injury". The old brief named the diagnosed brain injuries from the records.
   - Saw, minor: the headline says which shoulder, but none of its four facts names the side (1968 says only "second"). Sentence 2's chip, fact 286, does name it.
   - Mitigation: the ranked feed's ten include the defense exam (1864) and the limitations rule (233), so the page shows both below the brief.
   - Recommendation: fine for the demo, as it stands. Optionally, with the Manager's go-ahead, add one prompt line ("the biggest risk includes any defense pleaded and any defense medical exam that contradicts the claim") and run one brief call, about 5 cents. Owner: pipeline, Manager.

7. **With coverage limits on, a provider's page lists 9 limits with no policy names, and several look like duplicates.**
   - Where: `backend/app/services/provider_view.py:174-182`, which labels a limit by its basis only.
   - Saw: with every setting on, the chiropractic provider's preview lists:
     - "Policy limit per person" twice at one figure (1952 and 1975);
     - "Policy limit per occurrence" twice at one figure (1953 and 1976);
     - "Policy limit" three times (1956, 1985 and 2012);
     - the client's own UM/UIM limits.
   - Saw: the default leaves coverage limits off, so the default preview does not show this. Pass 1 #16 (no duplicate limits on the provider page) has come back in appearance since the limits were tagged by policy.
   - Expected: the provider sees the defendant's liability limit, labelled, once.
   - Owner: backend. The lead decides, since this changes the provider payload (Needs decision 3).

8. **The Case value and Medical specials tiles are right per D20. One small redundancy remains.**
   - Case value:
     - It leads with the Clio valuation (1931), and the basis line reads as the attorney's evaluation. There is no warning.
     - The recovery cap and the economic-damages total have left the tile. They are now facts 1964, 1977, 1994 and 2008 (recovery cap) and 1961 and 1992 (economic damages).
     - The second row is "At least" the same figure, from fact 1991. That fact's source states a single valuation, but the model filled only the low end.
     - Expected: one figure, with 1991 as a second source. Owner: backend, in `_case_value`: a one-ended value equal to the lead counts as another source for it. Pipeline could instead have a single valuation set both ends. Fine to leave.
   - Medical specials:
     - One figure, "Matches the sum of 175 bills", with six stated facts that agree (165, 183, 265, 288, 1932, 1960).
     - Fact 201's figure is now kind `economic_damages` (1992).
     - The nine providers with bills sum exactly to the tile's figure, and their totals have not changed. The tenth reads "No bills on file".
   - Firm spend: 5 expenses with new ids (1933 to 1937); the total has not changed.

9. **The re-read lost two caveats and moved a few facts between internal and shareable. Nothing an attorney relies on is gone.** (Before means the backup before (b), or before (a) for record 1.)

   | Record | Before | After | Lost or changed |
   |---|---|---|---|
   | 64, case evaluation | 12 | 11 | The caveat that the client's UM/UIM adds nothing above the defendant's limit (204) is now held by no fact, though the record says it. The policing and credibility point (207) is still held by facts 321 and 738 from other records. The radiology diagnosis (209) became kind `other` (1999) |
   | 58, no-fault exhausted | 5 | 4 | The specials fact with no amount (164), which said the specials are gross treatment value rather than a net claim. Two shareable facts (162, 163) folded into one internal fact (1983) |
   | 1, the matter | 29 | 30 | The mechanism of the incident (506) is still stated by many record facts. The "limits confirmed" checkbox fact (527) is now covered by 2002. The lien moved from internal to shareable (519 to 1965) |
   | 84, coverage confirmed | 8 | 9 | None. The misfiled case value (308) became a recovery cap (2008). The second defendant is new (2010) |
   | 48, defense coverage | 7 | 7 | The driver's coverage fact (104) folded into the limits that finding 2 mislabels |
   | 62, adjuster response | 6 | 7 | The limit lost its per-person basis (191 to 1985; finding 1) |
   | 109, no-fault letter | 2 | 3 | The limit lost its basis and gained no policy (376 to 2012; finding 1) |
   | 145, 146, defense emails | 4, 4 | 4, 4 | "No excess or umbrella coverage" moved from shareable coverage to internal `other` (469, 473 to 2017, 2021) |

   - Both visibility shifts away from internal are safe:
     - the limit from record 64 (203 to 1993) now shows no source to a provider (`provider_sources.py` opens only cited pages of a provider's own bills and records);
     - no lien fact has a provider, so no link releases one.
   - The shifts toward internal are conservative.

10. **Minor.**
    - The stored brief's `generated_at` still reads October 2. `f37a110` fixes later rewrites, and the screen does not show the date. The README already lists it.
    - The provider's "File opened" date is still two days from the header's opened date (Pass 1 #16).
    - The feed still lists the right-shoulder recommendation twice (196 and 1427; Pass 2 #10).

### Demo moments on the real matter

| # | Holds? | Notes |
|---|---|---|
| 1 | With a caveat | Every chip opens its source, and its quote is located in the source view. The scanned-page chip is behind "+2 more" (finding 3) |
| 2 | No, on one tile | Case value, Medical specials, Firm spend and the ten provider totals are right. Coverage shows the false warning and no lead (finding 1), and a mislabelled policy (finding 2) |
| 3 | Yes, with one false note | Off the link, the defendant's limit, economic damages, case value, the lien and the client's UM/UIM all lock. With coverage limits on, the shared limits are "supported". The provider's own bill total is "supported". The incident date reads "not in the file" (finding 4) |
| 4 | Yes | The default preview carries 207 facts and the all-on preview 490: all shareable, none flagged as strategy, none another provider's. Limits with coverage on: finding 7 |

### Rules that never bend

- **Read-only Clio:** `check.sh` at `f49469a` passes it (8 tests).
- **No case literals:** passes (4 tests).
- **Nothing private committed:** passes (4 tests). Lint, 371 backend tests and the frontend types also pass. No step failed.
- **Every fact sourced:** all 15 brief facts and all 25 Coverage facts have a source and a quote, and every quote is located. The open questions still state premises without chips (finding 6).
- **Provider boundary:** holds in the API (finding 7 is presentation only). Finding 5 is a latent gap.
- **No model on page load:** I made only GETs and the two in-memory POSTs, and the last digest run is still number 9.

### Needs decision (for the lead)

1. **Coverage conflict rule** (finding 1): **(1)**, with the lead kept as in (2). It is code only and can be done now.
2. **A policy value for another party's liability policy** (finding 2): add `other_party_liability` to D21's enum (additive), with a prompt line and a re-read of record 48. It costs a few cents and needs the Manager's go-ahead. Otherwise, document it as a known issue.
3. **Limits on a provider's page** (finding 7): show only the defendant's liability limit, labelled. Recommendation: yes. The client's own policies are the client's business, and they do not pay a lien.
4. **A date that is in the file but not on the link** (finding 4): give it a wording of its own, such as "In the file, not on this link", or count the incident date as supported. Recommendation: the first, plus counting the incident date as supported.
5. **The brief's risks** (finding 6): one prompt line and one brief call, about 5 cents. Recommendation: optional. The feed already shows both risks.

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
