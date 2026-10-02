# Track B: Firm view

**Owner:** [name]
**Read first:** `docs/ui.md`, the API routes and data model in `docs/architecture.md`
**Needs:** nothing but the repository. Start on `cli seed-dev`, switch to A's snapshot at S1.

## Status

- **Now:** B1
- **Blocked:** nothing

## Checklist

### B1 Firm endpoints (30 min)
- [ ] Matter header, actions, feed, timeline in `api/matters.py`, queries in `services/matter_queries.py`
- [ ] Fact source and page image in `api/facts.py`

### B2 Firm page (30 min)
- [ ] Shared pieces first, since Track C uses them: `SourceChip`, kind badge, money and date formatting
- [ ] Header, action board, ranked feed on seed data
- [ ] Leave the providers slot in the layout: render `ProvidersPanel` from Track C

### B3 Source drawer (25 min)
- [ ] Notes and emails with the quote highlighted
- [ ] Document pages with image, page number, previous and next
- [ ] `?fact=ID` in the URL
- [ ] **After S1: switch to the real snapshot and fix what breaks**

### B4 Brief, KPIs, injuries (35 min)
- [ ] Brief with chips per sentence and the open-questions list
- [ ] KPI strip, including the disagreement and not-found states
- [ ] Injuries list with page citations
- [ ] **After S3: check all three on real data**

### B5 Since you last opened (20 min)
- [ ] Changes endpoint, opened endpoint, seeded users, user switcher

### B6 Footer (10 min)
- [ ] Last sync time, digest cost, re-sync button, using Track A's ops endpoints

### B7 Timeline toggle (15 min, cut first)
- [ ] Full timeline grouped by month with kind filters and search

## Contract obligations

The shared components in `frontend/src/components/shared/` are used by Track C. Land them early in B2 and keep their props stable.

## Stubs and shortcuts

- Seeded stub users and `last_opened_at` values for the changes block.

## Known issues

- None yet.
