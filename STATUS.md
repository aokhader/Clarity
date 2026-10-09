# Status

Each role edits only its own row. Keep cells under 15 words. Update with /status. The hackathon's own status is history in docs/progress.md.

| Role | Now | Next | Blocked on | Needs decision | Updated |
|---|---|---|---|---|---|
| lead | D41 done: provider updates are stage moves only (the preview's dismissal label is gone, no link existed); litigation_event kind; pleadings re-read for $0.09 with the trial (P14); three court events in the story on the real matter, checked against their pages; provider screenshots retaken (c32693d) | Waiting for the reviewer's last README pass | | Manager: next full digest rewrites the brief (~$0.05); clip link; test call (C-T) | 19:06 |
| pipeline | P16 done (fbcc995): brief cites the suit and defense; notice dated; tiles unchanged; D42+D43 $0.37 | Standing by | | | 2026-10-08 20:29 |
| backend | B16: court events by type 63e64ab; undated list c891e7a (GET .../key-events/undated); 481 | Stand by | | Lead: looser cross-kind matcher? (see report) | 2026-10-08 20:33 |
| ui-builder | U18 a2b19cd checked; region rows keep the served-order tie-break | Stand by | | | 2026-10-08 20:41 |
| researcher | Done: briefs/model-pricing.md, paid-tier prices; unblocks lead and pipeline (P10, D34) | Idle | lead: commit model-pricing.md (no shell) | Manager: which paid provider and model for the runs | 2026-10-08 |
| critic | C5 done (0d60d65): brief omits limitations defense; story lacks first suit; court events doubled | Stand by | | Brief call for limitations; pin court rows by type; no note-date dating; refile one page | 2026-10-08 20:20 |
| reviewer | Done: upgrade-schema and reset in README (1ba8bb7); check.sh no FAIL, 466. Clone servers stopped | Standing by | | | 2026-10-08 19:09 |

## Stubs and shortcuts

New ones only, one line each when written: what, why, file. The hackathon's are in docs/progress.md and docs/tracks/*.md; the README lists both.

- B3: a sync or digest that fails before its run row is held in server memory, so a restart forgets it (backend/app/services/jobs.py)
- B1: the draft checker reads amounts only with $, USD or "dollars", and dates only with a month name or numeric form (backend/app/services/text_mentions.py)
- P6: a failed model call is not retried until `cli digest --retry-failed`; the run's error says how many were skipped (backend/app/digest/llm.py)
- P13: `cli reextract --dry-run` prices a selection from average recorded costs, an upper bound; cached answers cost less (backend/app/digest/reextract.py)
- C-P: a date said on a call without a year is placed at the nearest such day to the call, within six months, else left out (backend/app/digest/call_notes.py)
- P14: extract_record stays v3, so notes and emails still read court events as other; any bump re-reads the matter's custom fields, since their marker is the cache key (backend/app/digest/extract.py). Superseded by P15: notes and emails read with extract_note
- P15: a court event in a note is dated only by a date its text gives, never the note's own date, so 9 of 10 are undated and stay out of the story (backend/app/digest/prompts/extract_note.txt)
- P15: notes 48 and 62 were not re-read, since they hold policy limits behind the Coverage tile; 48's dismissal stays as other (backend/app/digest/extract.py)
- P14: `reextract --keep-brief` leaves the brief as it was; the next full digest writes it, one merge call (backend/app/cli.py)
- P14 run: the brief is kept and now stale against the facts, so the next digest (CLI or in-app) makes one Sonnet call (backend/app/digest/brief.py)
- P4 known issue: pages read before a provider was known never get that provider. Fix (1): store provider_name_as_written on facts (new column, needs reset or a migration), re-resolve in code after mapping, no model call. Fix (2): re-read pages when the provider list changes, one call per page (backend/app/digest/extract.py)
