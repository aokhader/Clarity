# Status

Each role edits only its own row. Keep cells under 15 words. Update with /status. The hackathon's own status is history in docs/progress.md.

| Role | Now | Next | Blocked on | Needs decision | Updated |
|---|---|---|---|---|---|
| lead | Verified U1 in the browser; the stored brief states a pre-fix bill total | Critic pass; next worker batches | Manager: re-digest go-ahead | Re-digest; headline citations; a read-time figure check on the brief | 01:20 |
| pipeline | P2 21fa27b, P4 1cd54d0, P5 9c05e39, P6 87a8546 done. P9: headline fact ids | P10 estimate, P11 brief input, P12 ledger titles | | Re-digest go-ahead (P10 estimate coming) | 00:58 |
| backend | B4 brief check. Note: 049da3d changed tile behaviour (one-ended value, occurrence limits, specials basis); B5 repairs | B5, B6, B7, B8, B9 | lead: restart :8000 if new routes 404; [tool.ruff] src=["."] in backend/pyproject.toml | | 01:05 |
| ui-builder | U8: states on demo screens, preview chips, drawer 'Uploaded', no-bills text | U7 after B4 | backend B4 (headline facts), B8 (document date), B9 (nullable billed_cents) | | 00:57 |
| researcher | Done: briefs/draft-checker.md (backend B1, ui-builder U4); briefs/calls.md (C-B, C-P, C-U) | Idle | lead: commit both briefs; researcher has no shell | Calls: let Manager type a test number, stored locally? | 01:05 |
| critic | C1 done: brief bills total unsourced; specials tile contradicts itself; IMEs conflated | C2 after the draft checker lands, and after the re-digest | | Re-digest won't re-extract or re-score; coverage tile mixes three policies | 00:56 |
| reviewer | | | | | |

## Stubs and shortcuts

New ones only, one line each when written: what, why, file. The hackathon's are in docs/progress.md and docs/tracks/*.md; the README lists both.

- B3: a sync or digest that fails before its run row is held in server memory, so a restart forgets it (backend/app/services/jobs.py)
- B1: the draft checker reads amounts only with $, USD or "dollars", and dates only with a month name or numeric form (backend/app/services/text_mentions.py)
