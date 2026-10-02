# Track C: Provider side

**Owner:** Abdulaziz Khader
**Read first:** the visibility section of `docs/architecture.md`, the share composer and provider view in `docs/ui.md`, `docs/submission.md`
**Needs:** nothing but the repository. Start on `cli seed-dev`, switch to A's snapshot at S1.

## Status

- **Now:** C3
- **Blocked:** nothing

## Checklist

### C1 Visibility filter (25 min)
- [x] `visible_facts_for_share` in `services/visibility.py`, default-deny
- [x] Tests: internal kinds never appear, another provider's bills never appear, off settings remove facts, hidden facts are removed, expired and revoked shares return nothing

### C2 Shares API and provider route (25 min)
- [x] Create, list, preview, patch, revoke in `api/shares.py`
- [x] `/api/p/{token}` and the provider source route in `api/provider.py`, recording an opened event
- [x] Preview and the token route call the same function

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

Track C also owns `services/provider_view.py`: the only module that builds a provider response, from `visible_facts_for_share`. `share_preview` and the provider link both call `provider_payload`.

## Decisions

- A provider opens a source only when their own bill or record cites a document page, and then sees only that page. Bills and records drawn from notes or emails show no source, since the source text may be internal.
- Case-level sections use neutral wording: the `status_change` label, "Policy limit per person", a yes or no for coverage. A case-level fact's title is never sent, since it can paraphrase an internal note.
- A task that raised a record request is the same ask; the provider sees it once.
- Unknown token is 404; expired or revoked is 410 with no data; a fact or page the share does not release is 404. Provider responses carry `Cache-Control: no-store`.
- Creating a share needs `X-User-Id` naming a stub user, and the contact must be a medical provider in the `field_mapping` digest.

## Stubs and shortcuts

- Provider access is by unguessable link only; there is no provider login.

## Known issues

- For Track A: store each fact's `visibility` with `services.visibility.fact_visibility(kind, mentions_strategy)`. The filter also requires the stored tag to be `shareable`, so a pipeline that leaves the default `internal` shares nothing (fails closed).
- The `requests` setting releases only open record requests and open tasks; fulfilled and completed ones stay internal.
- The dev database has no `users` rows until Track B seeds stub users (B5), so `POST /api/matters/{id}/shares` returns 401 there. The `X-User-Id` dependency lives in `api/shares.py` for now; B5 can move it somewhere shared.
- `firm_name` in the provider payload is always null: no synced record carries the firm's name.
