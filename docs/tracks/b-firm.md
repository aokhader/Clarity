# Track B: Firm view

**Owner:** Abdulaziz Khader
**Read first:** `docs/ui.md`, the API routes and data model in `docs/architecture.md`
**Needs:** nothing but the repository. Start on `cli seed-dev`, switch to A's snapshot at S1.

## Status

- **Now:** B4
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
- [ ] Brief with chips per sentence and the open-questions list
- [ ] KPI strip, including the disagreement and not-found states
- [ ] Injuries list with page citations
- [ ] **After S3: check all three on real data**

### B5 Since you last opened (20 min)
- [ ] Changes endpoint, opened endpoint, seeded users, user switcher; pass the current user to `ProvidersPanel`

### B6 Footer (10 min)
- [ ] Last sync time, digest cost, re-sync button, using Track A's ops endpoints

### B7 Timeline toggle (15 min, cut first)
- [ ] Full timeline grouped by month with kind filters and search

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

## Decisions

- Action board groups do not overlap: overdue, then waiting on others, then upcoming. A record request raised by a task already on the board is not listed twice. Past calendar entries are not overdue.
- Medical specials are cross-checked at read time against the sum of the bills; agreement merges the sources into one value, disagreement shows both.
- Timeline search matches at word starts, so "lien" finds liens and not every "client".
- Date-only strings are read as calendar days (`lib/format.ts`), since `new Date('2026-03-06')` shows March 5 in Pacific time.
- Case age is measured from the incident date, because the matter's open date is not a sourced fact and could not carry a chip.
- The drawer matches quotes ignoring whitespace and case, like the pipeline's quote check, and says so when a quote cannot be found instead of failing silently. Rich-text notes are shown as plain text, never as markup.
- Queries do not retry a 4xx, so an unsynced matter shows its message at once (`frontend/src/main.tsx`).

## Stubs and shortcuts

- Seeded stub users and `last_opened_at` values for the changes block.

## Known issues

- Corroborating-source tabs in the drawer are untested on data: the seed has no corroborating sources. Check them at S2.
- With the app window hidden, the browser pane stops painting, so the drawer's exit animation never ends and the closing overlay swallows the next click. Not seen in a visible window.
- On Windows, `uvicorn --reload` sometimes keeps serving the old code after a reload. Restart the server if a new route returns 404.
