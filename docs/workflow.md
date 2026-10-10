# Workflow rules

These rules exist because the build window is six hours, the repository is read by judges, and a wrong fact in front of a trial attorney ends the pitch.

## Each session

1. Start with `/kickoff <role>`, which reads your role file, `PLAN.md`, `STATUS.md` and `DECISIONS.md`. They say what is done, what is next, and what is blocked.
2. Take the next open item in `PLAN.md` that your role owns, unless told otherwise. Finish and verify it before starting another.
3. Before working in an area, read its context file (the table is in `CLAUDE.md`).
4. When an item is done, tick it in `PLAN.md` if you are the lead, or say so in your STATUS row, and record any shortcut in the STATUS stubs list. Use `/status`.
5. Before your context is cleared, write `HANDOFF.md` from `HANDOFF.md.example`, so the next session for your role loses nothing.

## How to build

- **Vertical slices.** Get one path working end to end (sync, fact, endpoint, component) before widening it. A thin working product at every commit is the goal.
- **Real endpoints from the first hour.** The frontend always talks to the real API. Before Track A's first snapshot, the database is filled by `cli seed-dev` with the synthetic matter; after it, by the snapshot. Do not create mock JSON in the frontend or return canned responses from an endpoint.
- **Verify by running.** After a backend change, call the endpoint and read the output. After a frontend change, load the page. After a pipeline change, run it and inspect the facts it wrote. Report what was observed, including failures. Do not describe work as done if it has not been run.
- **Small commits.** Commit each working slice with a message that states what now works. Push after each milestone. Judges read the history.
- **Stay in scope.** Do the item asked. Note unrelated problems in `docs/progress.md` under Known issues and leave them.

## Time discipline

- Each item has a budget in `PLAN.md`. If an item is taking twice its budget, stop and report the options: simplify, cut, or continue.
- Scope cuts follow the cut order in `PLAN.md`.
- After the freeze time in `PLAN.md` make no new features. Only fixes, the README, and checks.

## Decide or ask

Proceed without asking when the choice is local and reversible: naming, file placement inside the agreed layout, component structure, prompt wording.

Stop and ask before:

- changing or removing a field in the contract (`schemas.py` and `types.ts`); adding one is backend's call
- editing a path another role owns (`.claude/ownership.json`)
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

Several agent roles work at once in one checkout, on the `kit-trial` branch. The hackathon's track rules are history (`docs/parallel.md`). Now:

- Edit only the paths your role owns in `.claude/ownership.json`, plus your row in `STATUS.md`.
- Commit only your own paths with `git commit -m "..." -- <paths>`. Never `git add -A`. If git reports `index.lock`, wait a few seconds and retry.
- The contract is versioned by backend, not frozen: a change updates `schemas.py` and `types.ts` in one commit and is announced in STATUS.
- Everyone works on the real matter in `data/app.db`, which is gitignored and never committed. Re-syncing or re-digesting needs the Manager's go-ahead, since it costs money.
