# Status

Each role edits only its own row. Keep cells under 15 words. Update with /status. The hackathon's own status is history in docs/progress.md.

| Role | Now | Next | Blocked on | Needs decision | Updated |
|---|---|---|---|---|---|
| lead | D49 chat done (H0–H6), D50, D51; two live answers $0.148 and $0.030; check.sh no FAIL, 533 | Standing by | | Manager: Pass 6 follow-ups (stage date, date check, firm-wide cap); push | 2026-10-09 10:57 |
| pipeline | D53 (1), (3) done (4ea0a6e): stage undated unless set after record creation; chat_answer v2; 547 passed. Run: 2 Sonnet calls, $0.078 (est. $0.080), 0 errors; brief rewritten, cites renderable only; KPI values same; T2's 2 stage-date sentences withdrawn; backup `app.db.bak-20261009T210210Z-pre-d53` | Standing by | | | 2026-10-09 14:05 |
| backend | D54 done: table `chat_frozen_sources`; close freezes each cited source (sentence, figure-mark and item chips) as the drawer serves it, pages cut to the cited page; `GET /api/matters/{id}/chat/threads/{tid}/facts/{fact_id}/source` serves the copy (404 unless closed, in the matter, cited), backfills a pre-D54 thread on first open (404 'This source is no longer in the file.' if the fact is gone or its id now names a fact on another page); no contract type change; 560 passed. Checked on copies: real matter, 2 threads closed, 65 chips all 200, cut right; demo thread backfilled 3 of 3 | Standing by | | Lead: restart the API (new table) | 2026-10-09 14:33 |
| ui-builder | D54 done: closed thread's chips open the frozen route (`&frozen=`), drawer says "As cited when this thread was closed.", step keeps it, close drops it; headless 14/14, chat mocked | Lead: check in browser (demo, thread 1) | backend: freeze mention-mark chips too (`sentence.mentions[].facts`), else a closed thread's differs chip 404s | | 2026-10-09 14:31 |
| researcher | Done: briefs/model-pricing.md, paid-tier prices; unblocks lead and pipeline (P10, D34) | Idle | lead: commit model-pricing.md (no shell) | Manager: which paid provider and model for the runs | 2026-10-08 |
| critic | Pass 7 (H8, D52): stage date is Clio record creation, still misleads; T2 t3 S2 false "Not in file"; frozen chips break on re-read | Stand by | | Undate stage fact; source date counts as cited; freeze chip source+page | 2026-10-09 13:55 |
| reviewer | README for D54: frozen sources in Ask and Built, lightly tested (backend, lead, reviewer GETs), route, table, map; D53 half-done item removed; image limit and pre-D54 first-open gap (matches kind and page, not record) under Half-done; check.sh no FAIL, 560; Node tests SKIPPED (verified nothing) | Standing by | | backend/Manager: pre-D54 first-open check compares source type and page, not source id | 2026-10-09 14:39 |

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
- H2: the daily cap is read before a run starts, so questions asked at the same moment can each pass and overspend by one answer (backend/app/services/chat.py)
- H2: chat retrieval matches question words at word starts plus a fixed list of generic kind words; no embeddings, so a question in other words falls back to significance (backend/app/services/chat_context.py)
- H2: an item sends at most 50 facts, most significant first; restatements are added only for pointed-at facts (backend/app/services/chat_attachments.py). D50: the overview sends at most 20 facts, the leading one per KPI value, and the brief's cited facts only as room allows (backend/app/services/chat_context.py)
- D48: the firm view acts as the first seeded stub user, with no login and no switcher (frontend/src/api/users.ts)
- H3: dragging the Ask handle does not scroll the page at its edges; the wheel scrolls mid-drag, and pick mode reaches any row (frontend/src/components/ask/AskHandle.tsx)
- H3: Ask bar search hits show title, date and source type as text, no chip (an option cannot hold a button); chips open once asked (frontend/src/components/ask/AskBar.tsx)
- H1: a chat call any attempt of which the fallback answered is priced wholly at fallback rates, an upper bound (backend/app/digest/llm.py)
- H1: a response model named as the chat model plus an 8-digit date counts as the chat model, not the fallback (backend/app/digest/llm.py)
- H1: chat on openai or gemini sends its own output limit, but no effort and no fallback (backend/app/digest/llm.py)
