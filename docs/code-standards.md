# Code standards

Judges read this repository in a few minutes. Optimize for a reader who opens three files and decides whether the engineering is real.

## General

- Small modules with one job each, following the layout in `CLAUDE.md`. A file past roughly 300 lines is a sign to split.
- Names say what a thing is: `visible_facts_for_share`, not `filter2`.
- Comments explain why, where the reason is not obvious from the code. No commented-out code, no TODOs without an entry in `docs/progress.md`.
- No dead scaffolding: delete unused files, routes, and components before committing.
- Configuration comes from `config.py`. No literals for URLs, model names, prices, or limits anywhere else.
- No case-specific literals anywhere. This includes custom-field names, provider names, and document titles.

## Python

- Type hints on every function signature. Pydantic models at every boundary: API responses, model outputs, and parsed Clio records.
- SQLAlchemy 2 style with typed `Mapped` columns. One session per request through a FastAPI dependency; one session per CLI command.
- Route handlers are thin. They call a function in a service module and return a schema. Queries and business rules do not live in handlers.
- Errors: raise specific exceptions (`ClioWriteForbidden`, `ClioRateLimited`, `ExtractionFailed`). In batch stages, catch per item, record the error, and continue. Never use a bare `except`.
- Logging through the `logging` module with one line per event and counts at the end of each stage. No `print` outside `cli.py`.
- Format and lint with ruff using default settings.
- Money is stored as integer cents or `Decimal`, never float. Dates are ISO strings in JSON and `date` or timezone-aware `datetime` in Python.

## TypeScript and React

- `strict` on. No `any`; use `unknown` and narrow.
- API types live in `src/api/types.ts` and mirror `schemas.py`. All fetching goes through hooks in `src/api/` built on TanStack Query. Components do not call `fetch`.
- Function components only. Props typed inline or with a named type above the component.
- One component per file, named for what it shows. Pages compose components and hold no data logic.
- Styling with Tailwind classes and theme tokens. No inline hex colors and no separate CSS files beyond the Tailwind entry.
- Format money and dates through helpers in `src/lib/format.ts` so they are consistent everywhere.
- Every chip, button, and row that can be clicked is a real button or link with a label, so keyboard and screen-reader use work.

## Tests

Time is short, so test where a bug would be fatal and skip the rest.

Required:

- `visible_facts_for_share`: internal kinds never appear; another provider's bills never appear; off settings remove their facts; hidden facts are removed; expired and revoked shares return nothing.
- Clio client: any non-GET raises; paging follows `next` to the end; a 429 waits and retries.
- `verify.py`: a fact whose quote is not in the input is dropped; disagreeing second reads produce low confidence.

Fixtures are synthetic and generic. No content from the real matter in the test suite.

## Git

- Commit messages in the imperative, stating what now works: "Extract facts from scanned pages with page citations".
- `.env` and `data/` are ignored. Check `git status` before every commit.
- Keep `README.md` accurate at each milestone: how to run, what works, what is stubbed.
