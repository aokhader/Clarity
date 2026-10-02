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
- `Panel({ title, icon?, aside?, actions?, className?, children })`: a white card with an optional lucide icon before a bold heading
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

- The firm page follows the Clarity Dashboard v2 design, built after the submission close at the owner's call. A dark sidebar switches four views through `?view=` (`lib/matterViews.ts`): Case Overview (client card, case metadata, brief, roadmap), For Attorney (action board with counts and a task table, What Matters, injuries, providers, figures), For Service Provider, and Documents. Source chips stay on every fact, revealed on hover, though the mockup drops them (rule 3). The theme tokens in `frontend/src/index.css`, a contract file, changed to the design's slate and blue; the shared `Panel` restyle also reaches the provider page.
- For Service Provider shows what a chosen provider's link would release with the default settings, from Track C's draft-preview endpoint and `ProviderView`. The server filter decides the content, so the firm's preview cannot show more than the provider would see. The mockup's tickable action requests are not built: they would need a write path the API does not have.
- Case metadata picks the most significant liability fact, the most significant injury, and the statute of limitations among deadlines whose type names it (`statuteDeadline` in `lib/facts.ts`): the next one ahead, or the latest passed. The action table and injuries list show 8 and 6 rows before "Show all", since the real matter has 75 open items and 321 injuries.
- Chips in the header, stage pill, Financial overview, and brief appear only on hover or keyboard focus of their fact, at the owner's request for a cleaner page (`components/firm/RevealOnHover.tsx`). They stay in the layout and tab order, so every fact is still one click from its source.
- A Documents page (`?view=documents`, linked from the sidebar) lists every cited source once, grouped by source type with filter pills; each fact opens the source drawer. It is built from the timeline endpoint, so it needed no new route or schema; a source shows its facts, since `FactOut` carries no source title.
- On the provider page (and both firm previews, which share `ProviderView`), bills and records each show 10 rows and scroll the rest, under a "Total billed by your office" headline. These are Track C files (`components/share/ProviderItemList.tsx`, `ProviderView.tsx`, new `BillsTotal.tsx`), changed at the owner's request after the close. Row height is measured, not assumed, because long labels wrap.
- Each provider's charges count once (`backend/app/services/bills.py`). The same charges reach the store as itemized bills from the provider's documents, a ledger entry in Clio, and totals stated in notes, and adding them counted the real matter's bills three times ($349,650). Per provider the most complete record is counted, the itemized bills whenever they account for it, since each cites a page; a note that states a provider's total without naming the provider is that bill again. The providers panel, the specials tile, the provider page, and the digest's cross-check and brief figures all use it. On the real matter the bills now total $118,400, the firm's own specials figure. Fixed after the close at the owner's request; it also covers Track A's review finding on double-counted bills.
- The provider payload gained `bills_total` (`ProviderBillsTotalOut`: amount and count), a contract change made in one commit across `schemas.py` and `types.ts`. The page cannot add up its own list, because that list also holds liens on the same charges. The list now leaves out the records that restate the counted bills.
- Action board rows carry no chip: the whole row is one button that opens the task's source in the drawer, at the owner's request. A low-confidence item keeps its dashed amber marker as a tag on the row, since the chip used to carry it.

## Stubs and shortcuts

- Seeded stub users (Demo Attorney, Demo Paralegal, Demo Case Manager) chosen by a header switcher; no real login. (`backend/app/services/users.py`, `frontend/src/components/firm/UserSwitcher.tsx`)
- Seeded "last opened" dates, applied the first time a stub user opens a matter: 21 days ago, 7 days ago, and never. (`backend/app/services/users.py`, `backend/app/services/visits.py`)
- The brief shows only its headline and open questions; the sentence body is not displayed, at the owner's request after the freeze (`frontend/src/components/firm/Brief.tsx`). The headline carries no source chip, which departs from rule 3; the facts behind it are reachable from the timeline and the Documents page.

## Known issues

- Re-sync runs Track A's sync, which pulls the matter named by `CLIO_MATTER_QUERY`, not necessarily the one on screen. Fine for a one-matter demo.
- Each visit uses up the changes block. To replay it for another clip take, run `cli seed-dev` (synthetic matter) or delete the `views` rows for the real matter.
- Track A updates the brief digest in place, so `digests.created_at` (the API's `generated_at`) is the first generation time, not the latest. The UI does not show it.
- Corroborating-source tabs in the drawer are untested on data: the seed has no corroborating sources. Check them at S2.
- With the app window hidden, the browser pane stops painting, so the drawer's exit animation never ends and the closing overlay swallows the next click. Not seen in a visible window.
- On Windows, `uvicorn --reload` sometimes keeps serving the old code after a reload. Restart the server if a new route returns 404.
