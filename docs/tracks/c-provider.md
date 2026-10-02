# Track C: Provider side

**Owner:** [name]
**Read first:** the visibility section of `docs/architecture.md`, the share composer and provider view in `docs/ui.md`, `docs/submission.md`
**Needs:** nothing but the repository. Start on `cli seed-dev`, switch to A's snapshot at S1.

## Status

- **Now:** C1
- **Blocked:** nothing

## Checklist

### C1 Visibility filter (25 min)
- [ ] `visible_facts_for_share` in `services/visibility.py`, default-deny
- [ ] Tests: internal kinds never appear, another provider's bills never appear, off settings remove facts, hidden facts are removed, expired and revoked shares return nothing

### C2 Shares API and provider route (25 min)
- [ ] Create, list, preview, patch, revoke in `api/shares.py`
- [ ] `/api/p/{token}` and the provider source route in `api/provider.py`, recording an opened event
- [ ] Preview and the token route call the same function

### C3 Provider page (30 min)
- [ ] Status tracker, coverage, requests, bills and records, updates, firm note
- [ ] Expired and revoked states
- [ ] **After S1: switch to the real snapshot and fix what breaks**

### C4 Providers panel (20 min)
- [ ] Providers endpoint with totals and share status
- [ ] `ProvidersPanel` for the firm page: share and opened status, Share button

### C5 Share composer (35 min)
- [ ] Section toggles, per-item hide, note, expiry
- [ ] Live preview using the provider page components
- [ ] If behind: replace with a one-click share using default settings

### C6 Submission material (30 min, start by 2:30 PM at the latest)
- [ ] README from the outline in `docs/submission.md`
- [ ] Draft form answers; collect every track's stubs and known issues
- [ ] Rehearse the clip script on the integrated build

## Contract obligations

The visibility function is the security boundary. No other code path may assemble a provider response. Changing a visibility rule needs the team's agreement.

## Stubs and shortcuts

- Provider access is by unguessable link only; there is no provider login.

## Known issues

- None yet.
