# Workflow rules

These rules exist because the build window is six hours, the repository is read by judges, and a wrong fact in front of a trial attorney ends the pitch.

## Each session

1. Read `docs/progress.md` and your track file in `docs/tracks/` first. They say what is done, what is next, and what is blocked.
2. Take the next unchecked item in your track unless told otherwise. Finish and verify it before starting another.
3. Before working in an area, read its context file (the table is in `CLAUDE.md`).
4. When an item is done, update your track file in the same commit: check the box, move the "Now" line, and record any shortcut. `docs/progress.md` holds shared state and changes only at sync points.
5. Keep the track file current enough that the conversation can be cleared at any point without losing state.

## How to build

- **Vertical slices.** Get one path working end to end (sync, fact, endpoint, component) before widening it. A thin working product at every commit is the goal.
- **Real endpoints from the first hour.** The frontend always talks to the real API. Before Track A's first snapshot, the database is filled by `cli seed-dev` with the synthetic matter; after it, by the snapshot. Do not create mock JSON in the frontend or return canned responses from an endpoint.
- **Verify by running.** After a backend change, call the endpoint and read the output. After a frontend change, load the page. After a pipeline change, run it and inspect the facts it wrote. Report what was observed, including failures. Do not describe work as done if it has not been run.
- **Small commits.** Commit each working slice with a message that states what now works. Push after each milestone. Judges read the history.
- **Stay in scope.** Do the item asked. Note unrelated problems in `docs/progress.md` under Known issues and leave them.

## Time discipline

- Each item has a budget in its track file. If an item is taking twice its budget, stop and report the options: simplify, cut, or continue.
- Scope cuts follow the tiers in `docs/project.md`, bottom first.
- After 3:15 PM PT make no new features. Only fixes, the README, and submission material.

## Decide or ask

Proceed without asking when the choice is local and reversible: naming, file placement inside the agreed layout, component structure, prompt wording.

Stop and ask before:

- changing any contract file after M0 (the list is in `docs/parallel.md`)
- editing a path another track owns
- adding a dependency that is not in the stack list
- changing a visibility rule or the provider payload
- cutting or adding a feature
- anything that would send a non-GET request to Clio

When a Clio field or parameter is uncertain, look it up in `docs/reference/clio-openapi.json`. Do not guess and do not probe the live API with trial requests, since each one counts against the rate limit.

## Honesty about shortcuts

The submission form asks what is half-done or hardcoded, and the screeners check. Every stub, seed, fallback, or simplification goes in the "Stubs and shortcuts" section of your track file at the moment it is written, with the file where it lives. Seeded demo users and their last-opened dates are the known example.

Never make a feature appear to work by writing its expected output into the code.

## Models and data

- All model calls go through `digest/llm.py`, so they are cached and costed.
- Prompts live in `digest/prompts/` as files and carry a version string that is part of the cache key.
- No request handler calls a model.
- Secrets stay in `.env`. Never print tokens or commit `.env` or `data/`.
- The case file contains a real person's medical and legal details. Do not paste its contents into commit messages, the README, test fixtures, or logs at info level.

## Parallel work

Three people work three tracks at once after M0. The rules that keep that safe are in `docs/parallel.md`. In short:

- Edit only the paths your track owns.
- Contract files are frozen after M0. A change needs the team's agreement and one commit that updates every mirror.
- Work on `main`, commit small, and run `git pull --rebase` before every push.
- Tracks B and C run on the synthetic seed until Track A publishes a snapshot, then on the snapshot. Snapshots hold real case data and are never committed.
