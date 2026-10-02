# Track B: Firm view

**Owner:** Abdulaziz Khader
**Read first:** `docs/ui.md`, the API routes and data model in `docs/architecture.md`
**Needs:** nothing but the repository. Start on `cli seed-dev`, switch to A's snapshot at S1.

## Status

- **Now:** B1 to B7 built. Next: switch to Track A's data at S1 to S3 and fix what breaks
- **Blocked:** nothing

## Checklist

### B1 Firm endpoints (30 min)
- [x] Matter header, actions, feed, timeline in `api/matters.py`, queries in `services/matter_queries.py`
- [x] Fact source and page image in `api/facts.py`

### B2 Firm page (30 min)
- [x] Shared pieces first, since Track C uses them: `SourceChip`, kind badge, money and date formatting
- [x] Header, action board, ranked feed on seed data
- [x] Leave the providers slot in the layout: render `ProvidersPanel` from Track C (gets `userId={null}` until the B5 switcher, so Share stays disabled)

### B3 Source drawer (25 min)
- [x] Notes and emails with the quote highlighted
- [x] Document pages with image, page number, previous and next
- [x] `?fact=ID` in the URL
- [ ] **After S1: switch to the real snapshot and fix what breaks**

### B4 Brief, KPIs, injuries (35 min)
- [x] Brief with chips per sentence and the open-questions list
- [x] KPI strip, including the disagreement and not-found states
- [x] Injuries list with page citations
- [ ] **After S3: check all three on real data**

### B5 Since you last opened (20 min)
- [x] Changes endpoint, opened endpoint, seeded users, user switcher; pass the current user to `ProvidersPanel`

### B6 Footer (10 min)
- [x] Last sync time, digest cost, re-sync button, using Track A's ops endpoints (live since Track A merged at `f94db18`; the footer also shows per-item failures from `stats.errors`, which leave the run's own `error` empty)

### B7 Timeline toggle (15 min, cut first)
- [x] Full timeline grouped by month with kind filters and search

## Contract obligations

The shared components in `frontend/src/components/shared/` are used by Track C. Land them early in B2 and keep their props stable. Current props:

- `SourceChip({ fact: FactRef, className? })`: opens the source drawer by setting `?fact=ID`; dashed amber outline for low confidence
- `SourceChipList({ facts: FactRef[], max = 3 })`: chips, with "+N more" past `max`
- `KindBadge({ kind: FactKind })`
- `Panel({ title, aside?, actions?, className?, children })`: titled section with small-caps heading
- `LoadError({ what, error, onRetry })`: the error state with a retry button
- `lib/format.ts` (`formatMoney`, `formatMoneyRange`, `formatDate`, `formatDateTime`, `daysFromToday`, `formatDaysAgo`, `formatElapsed`), `lib/labels.ts` (kind, source, stage, and waiting-on labels), `lib/useSourceDrawer.ts`

Track B also owns these service modules, added in B1:

- `services/fact_views.py`: `renderable_facts`, the one query every firm view starts from (it drops document facts without a page and quote), and the `FactOut` and `FactRef` serializers
- `services/kpis.py`: the four KPI tiles
- `services/source_views.py`: the source drawer and page-image lookup
- `services/clio_records.py`: lenient Pydantic models over raw Clio JSON; Track A may reuse them
- `services/brief_view.py`: the stored brief with its citations checked
- `services/users.py` and `services/visits.py`: the stub users and the "since you last opened" queries

## Decisions

- Action board groups do not overlap: overdue, then waiting on others, then upcoming. A record request raised by a task already on the board is not listed twice. Past calendar entries are not overdue.
- Medical specials are cross-checked at read time against the sum of the bills; agreement merges the sources into one value, disagreement shows both.
- Timeline search matches at word starts, so "lien" finds liens and not every "client".
- Date-only strings are read as calendar days (`lib/format.ts`), since `new Date('2026-03-06')` shows March 5 in Pacific time.
- Case age is measured from the incident date, because the matter's open date is not a sourced fact and could not carry a chip.
- The drawer matches quotes ignoring whitespace and case, like the pipeline's quote check, and says so when a quote cannot be found instead of failing silently. Rich-text notes are shown as plain text, never as markup.
- A brief sentence is shown only if every fact it cites can be shown; otherwise part of it would be unsourced. Track A already drops sentences that cite unknown facts; this also covers facts that exist but cannot render.
- With no stage fact from Clio, the header shows the brief's stage marked "inferred", with the brief's stage citations. With no citation either, it shows "Stage not found in file".
- In the brief, each sentence's last word and its chips wrap as a unit, so a chip never starts a line as if it belonged to the next sentence.
- A visit is recorded once the page has loaded this visit's changes, and the list stays as loaded until the next visit. `docs/project.md` says leaving the page records it, but a request on leave cannot carry the `X-User-Id` header (`sendBeacon`), and React's dev-mode double effects would record it the moment the page opens.
- Stub users are seeded in `init_db` (`backend/app/db.py`), so Track C's share endpoints find them on a fresh database. `api/client.ts` gained an optional `userId` and `apiPost`; both additive.
- Queries do not retry a 4xx, so an unsynced matter shows its message at once (`frontend/src/main.tsx`).

- The firm page takes the Clarity Dashboard v2 look (dark section rail, icon-headed cards, tinted KPI tiles) after the freeze, at the owner's call, restyle only. Source chips stay, though the mockup drops them (rule 3). This changed the theme tokens in `frontend/src/index.css`, a contract file; the shared `Panel` restyle also reaches the provider page.
- Chips in the header, stage pill, Financial overview, and brief appear only on hover or keyboard focus of their fact, at the owner's request for a cleaner page (`components/firm/RevealOnHover.tsx`). They stay in the layout and tab order, so every fact is still one click from its source.
- A Documents page (`?view=documents`, linked from the sidebar) lists every cited source once, grouped by source type with filter pills; each fact opens the source drawer. It is built from the timeline endpoint, so it needed no new route or schema; a source shows its facts, since `FactOut` carries no source title.

## Stubs and shortcuts

- Seeded stub users (Demo Attorney, Demo Paralegal, Demo Case Manager) chosen by a header switcher; no real login. (`backend/app/services/users.py`, `frontend/src/components/firm/UserSwitcher.tsx`)
- Seeded "last opened" dates, applied the first time a stub user opens a matter: 21 days ago, 7 days ago, and never. (`backend/app/services/users.py`, `backend/app/services/visits.py`)

## Known issues

- Re-sync runs Track A's sync, which pulls the matter named by `CLIO_MATTER_QUERY`, not necessarily the one on screen. Fine for a one-matter demo.
- Each visit uses up the changes block. To replay it for another clip take, run `cli seed-dev` (synthetic matter) or delete the `views` rows for the real matter.
- Track A updates the brief digest in place, so `digests.created_at` (the API's `generated_at`) is the first generation time, not the latest. The UI does not show it.
- Corroborating-source tabs in the drawer are untested on data: the seed has no corroborating sources. Check them at S2.
- With the app window hidden, the browser pane stops painting, so the drawer's exit animation never ends and the closing overlay swallows the next click. Not seen in a visible window.
- On Windows, `uvicorn --reload` sometimes keeps serving the old code after a reload. Restart the server if a new route returns 404.
