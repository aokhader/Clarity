# Status

Each role edits only its own row. Keep cells under 15 words. Update with /status. The hackathon's own status is history in docs/progress.md.

| Role | Now | Next | Blocked on | Needs decision | Updated |
|---|---|---|---|---|---|
| lead | Verified Calls in the browser (targets, chips, typed line, no-model notes, consent gate), No bills on file, coverage tile | Critic Pass 2 findings; then freeze and the reviewer | Manager: .env model settings; the test call (C-T) | Approve (a), (b), a re-sync; retry-failed button | 02:05 |
| pipeline | C-P done 9bd8566 113fdef. Backend: extract_call_notes(session, transcript, *, matter_id, call_date, counterpart, retry_failed) -> CallNotes(notes, dropped). CallNoteDraft: kind, text, quote, quote_start, quote_end, amounts_cents, dates [{on, precision}]. Raises ModelsNotConfigured (no_model), CallNotesFailed (failed) | Idle; report to lead | Manager: .env lacks models and prices; (a), (b) wait on D24 upgrade_schema | P10: (a) ~$0.20; (b) ~$0.19 | 01:47 |
| backend | 9b176f6: call notes dropped count fixed; storing errors now fail the call. Standing by for critic Pass 2 | Critic Pass 2 findings | ui-builder: labels.ts call_note and call; ProviderRow.tsx:37 null billed_cents (typecheck red) | | 01:52 |
| ui-builder | Consent Cancel 02ea04b; Calls, U9, drawer date done | Stand by for critic Pass 2 | | | 01:56 |
| researcher | Done: briefs/draft-checker.md (backend B1, ui-builder U4); briefs/calls.md (C-B, C-P, C-U) | Idle | lead: commit both briefs; researcher has no shell | Calls: let Manager type a test number, stored locally? | 01:05 |
| critic | C2 done: Case value leads with recovery cap; lock bypassed; incident date falsely locked | Pass 3 after the re-digest (D13) | | Incident date shareable? Near-figure flag; coincident dates warn, not lock | 01:58 |
| reviewer | | | | | |

## Stubs and shortcuts

New ones only, one line each when written: what, why, file. The hackathon's are in docs/progress.md and docs/tracks/*.md; the README lists both.

- B3: a sync or digest that fails before its run row is held in server memory, so a restart forgets it (backend/app/services/jobs.py)
- B1: the draft checker reads amounts only with $, USD or "dollars", and dates only with a month name or numeric form (backend/app/services/text_mentions.py)
- P9: headline_fact_ids is written beside BriefContent's fields until backend adds it to the contract (backend/app/digest/merge.py)
- P6: a failed model call is not retried until `cli digest --retry-failed`; the run's error says how many were skipped (backend/app/digest/llm.py)
- P13: `cli reextract --dry-run` prices a selection from average recorded costs, an upper bound; cached answers cost less (backend/app/digest/reextract.py)
- C-P: a date said on a call without a year is placed at the nearest such day to the call, within six months, else left out (backend/app/digest/call_notes.py)
- P4 known issue: pages read before a provider was known never get that provider. Fix (1): store provider_name_as_written on facts (new column, needs reset or a migration), re-resolve in code after mapping, no model call. Fix (2): re-read pages when the provider list changes, one call per page (backend/app/digest/extract.py)
