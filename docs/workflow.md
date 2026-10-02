# Workflow rules

These rules exist because the build window is six hours, the repository is read by judges, and a wrong fact in front of a trial attorney ends the pitch.

## Each session

1. Read `docs/progress.md` first. It says what is done, what is next, and what is blocked.
2. Take the next unchecked item in the current milestone unless told otherwise. Finish and verify it before starting another.
3. Before working in an area, read its context file (the table is in `CLAUDE.md`).
4. When an item is done, update `docs/progress.md` in the same commit: check the box, move the "Now" line, and record any decision or shortcut.
5. Keep `docs/progress.md` current enough that the conversation can be cleared at any point without losing state.

## How to build

- **Vertical slices.** Get one path working end to end (sync, fact, endpoint, component) before widening it. A thin working product at every commit is the goal.
- **Real data from the first hour.** Build against the synced matter. Do not create mock JSON for the frontend; if an endpoint is not ready, build the endpoint.
- **Verify by running.** After a backend change, call the endpoint and read the output. After a frontend change, load the page. After a pipeline change, run it and inspect the facts it wrote. Report what was observed, including failures. Do not describe work as done if it has not been run.
- **Small commits.** Commit each working slice with a message that states what now works. Push after each milestone. Judges read the history.
- **Stay in scope.** Do the item asked. Note unrelated problems in `docs/progress.md` under Known issues and leave them.

## Time discipline

- Each milestone has a budget in `docs/progress.md`. If an item is taking twice its share, stop and report the options: simplify, cut, or continue.
- Scope cuts follow the tiers in `docs/project.md`, bottom first.
- After 3:15 PM PT make no new features. Only fixes, the README, and submission material.

## Decide or ask

Proceed without asking when the choice is local and reversible: naming, file placement inside the agreed layout, component structure, prompt wording.

Stop and ask before:

- changing the database schema after M2
- adding a dependency that is not in the stack list
- changing a visibility rule or the provider payload
- cutting or adding a feature
- anything that would send a non-GET request to Clio

When a Clio field or parameter is uncertain, look it up in `docs/reference/clio-openapi.json`. Do not guess and do not probe the live API with trial requests, since each one counts against the rate limit.

## Honesty about shortcuts

The submission form asks what is half-done or hardcoded, and the screeners check. Every stub, seed, fallback, or simplification goes in the "Stubs and shortcuts" section of `docs/progress.md` at the moment it is written, with the file where it lives. Seeded demo users and their last-opened dates are the known example.

Never make a feature appear to work by writing its expected output into the code.

## Models and data

- All model calls go through `digest/llm.py`, so they are cached and costed.
- Prompts live in `digest/prompts/` as files and carry a version string that is part of the cache key.
- No request handler calls a model.
- Secrets stay in `.env`. Never print tokens or commit `.env` or `data/`.
- The case file contains a real person's medical and legal details. Do not paste its contents into commit messages, the README, test fixtures, or logs at info level.

## Parallel work

The backend and the frontend can move in parallel once the response schemas in `backend/app/schemas.py` are settled, with `frontend/src/api/types.ts` mirroring them. Whoever changes a schema changes both files in one commit.
