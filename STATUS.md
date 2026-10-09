# Status

Each role edits only its own row. Keep cells under 15 words. Update with /status. The hackathon's own status is history in docs/progress.md.

| Role | Now | Next | Blocked on | Needs decision | Updated |
|---|---|---|---|---|---|
| lead | D44-D48 for the Manager: reading face, story lanes, Calls column, Overview cards, every "+N more" steps through sources, story newest first, Deadlines and follow-ups, "Viewing as" switcher removed | Standing by | | Manager: push; clip link; test call (C-T); reviewer: README and form answers still describe the switcher, "oldest first" and "Now strip"; screenshots | 2026-10-09 00:54 |
| pipeline | H1 done (48af6d2): chat role, digest/chat.py answer_question, prompt v1; 496 passed | Standing by | | | 2026-10-09 01:29 |
| backend | B16: court events by type 63e64ab; undated list c891e7a (GET .../key-events/undated); 481 | Stand by | | Lead: looser cross-kind matcher? (see report) | 2026-10-08 20:33 |
| ui-builder | D45 drawer bfe1ebf: quote callout, text in paragraphs/lists, field grid plus prose | Lead: check drawer in browser | | Measure 32em, not 68ch (68ch gave ~90 chars) | 2026-10-09 00:33 |
| researcher | Done: briefs/model-pricing.md, paid-tier prices; unblocks lead and pipeline (P10, D34) | Idle | lead: commit model-pricing.md (no shell) | Manager: which paid provider and model for the runs | 2026-10-08 |
| critic | C5 done (0d60d65): brief omits limitations defense; story lacks first suit; court events doubled | Stand by | | Brief call for limitations; pin court rows by type; no note-date dating; refile one page | 2026-10-08 20:20 |
| reviewer | README: ten screenshots, captions checked (aecba2f); check.sh no FAIL, 481; Node tests SKIPPED | Standing by; clone still serving :8010, :5183 | | | 2026-10-08 21:34 |

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
- D47: the drawer steps through at most 1,000 sources of one item; a longer list stops at the 1,000th, and its count reads 1,000 (frontend/src/lib/useSourceDrawer.ts)
- D48: the firm view acts as the first seeded stub user, with no login and no switcher (frontend/src/api/users.ts)
- H1: a chat call any attempt of which the fallback answered is priced wholly at fallback rates, an upper bound (backend/app/digest/llm.py)
- H1: a response model named as the chat model plus an 8-digit date counts as the chat model, not the fallback (backend/app/digest/llm.py)
- H1: chat on openai or gemini sends its own output limit, but no effort and no fallback (backend/app/digest/llm.py)
