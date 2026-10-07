# Status

Each role edits only its own row. Keep cells under 15 words. Update with /status. The hackathon's own status is history in docs/progress.md.

| Role | Now | Next | Blocked on | Needs decision | Updated |
|---|---|---|---|---|---|
| lead | Workers started: pipeline, backend, ui-builder, researcher; servers up | Critic pass at T+1:00; verify U1 in the browser | | | 00:40 |
| pipeline | Done: P8 23e23dc, P1 0f0bbf8, P3 b988547; 112 tests pass | Awaiting next item from lead | lead: same ruff src fix as backend; --fix from root would break imports | Manager: re-digest so new prompt versions apply? Costs merge calls | 00:39 |
| backend | B3 done daff938: contract adds RunStatusOut.start_failure; ui-builder can show it. Now B2 | B2 KPI check, B1 draft checker | lead: add [tool.ruff] src=["."] to backend/pyproject.toml; fixes all 13 I001 | | 00:38 |
| ui-builder | U1 done 83ad882; U2: checking drawer, brief, KPIs, injuries on real data | U3 provider page check | | Brief headline has no fact ids, so no chip (rule 3) | 00:35 |
| researcher | R0 written, docs/briefs/draft-checker.md: unblocks backend B1, ui-builder U4. Now R1 | R1 calls brief | lead: commit briefs, researcher has no shell | | 00:55 |
| critic | | | | | |
| reviewer | | | | | |

## Stubs and shortcuts

New ones only, one line each when written: what, why, file. The hackathon's are in docs/progress.md and docs/tracks/*.md; the README lists both.

- 
