# Status

Each role edits only its own row. Keep cells under 15 words. Update with /status. The hackathon's own status is history in docs/progress.md.

| Role | Now | Next | Blocked on | Needs decision | Updated |
|---|---|---|---|---|---|
| lead | D49 chat built (H0–H4) and D50 fixes in; one live question $0.148 before the trim | Second live question; critic and reviewer passes (H5) | | Manager: go-ahead for the second live question | 2026-10-09 10:28 |
| pipeline | D50 (2) done (55a564e): chat input compact JSON, items cut to CHAT_ITEM_FACTS=25 most significant, chat rows without significance, CHAT_CONTEXT_FACTS=40, an INFO line when a call needs a second attempt; brief input unchanged; sent size 76,357 to 37,205 chars (KPI tile) and 58,341 to 29,854 (no item), with backend's overview cap; 529 passed | Standing by | lead: `.env.example` gets `CHAT_ITEM_FACTS=25` and `CHAT_CONTEXT_FACTS=40`; backend: `context_fact_ids` could use `chat.shown_item_facts` so the audit trail lists only the item facts the model saw | | 2026-10-09 10:21 |
| backend | Logging fix done: at startup `main.configure_app_logging()` gives the `app` logger INFO and one stream handler when no handler reaches it (uvicorn), and changes nothing under the CLI or pytest; httpx stays WARNING; uvicorn loggers untouched; brief_view's invalid-brief warning logs field paths, not the error text; no contract change; 533 passed | Standing by | | Lead: the server needs a restart to pick it up | 2026-10-09 10:43 |
| ui-builder | D50 (1) done: Ask bar one line, 36px at rest at 1440 and 320 (was 86, 102); items and starters on a second line only while attached; tested headless, chat mocked | Lead: check in browser | | | 2026-10-09 10:25 |
| researcher | Done: briefs/model-pricing.md, paid-tier prices; unblocks lead and pipeline (P10, D34) | Idle | lead: commit model-pricing.md (no shell) | Manager: which paid provider and model for the runs | 2026-10-08 |
| critic | C5 done (0d60d65): brief omits limitations defense; story lacks first suit; court events doubled | Stand by | | Brief call for limitations; pin court rows by type; no note-date dating; refile one page | 2026-10-08 20:20 |
| reviewer | H5 README done: Ask view, chat cost, data out, stubs, map, D44–D48 fixes; check.sh no FAIL, 533; Node tests SKIPPED | Standing by; clone servers stopped | | | 2026-10-09 10:50 |

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
