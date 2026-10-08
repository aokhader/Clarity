# UI

## Principles

1. **A brief, not a dashboard of tiles.** The first thing on screen is the story of the case in sentences. The brief says existing tools fail because they show "counts and lists" and leave the story to be assembled by hand.
2. **Everything is clickable evidence.** Every date, amount, and claim is a chip that opens its source. Text with no source is limited to labels and headings.
3. **Two depths.** The default view fits 90 seconds. One toggle opens the full timeline.
4. **No chat box.** The user should not need to know what to ask.
5. **Honest uncertainty.** Low-confidence facts carry a visible marker. Disagreeing sources show both values. Missing data says "Not found in file".
6. **Built to be filmed.** The clip is 90 seconds and the judges see it on a projector. Use large type for the brief, strong contrast, and a 1440 by 900 desktop layout. There is no separate mobile design, but every view reflows down to 320 CSS px so it survives 200% and 400% zoom (WCAG 1.4.10).
7. **The 90-second test (D38).** The Overview's first screen at 1440 by 900 answers at least 9 of these, and one scroll answers all 12: what kind of case; when it happened; what happened; the injuries; whether the client is still treating; the stage; value against coverage; the statute; what is overdue, next or waited on; the last client contact; what changed lately; what has happened so far, in order.

## Visual direction

The audience is trial attorneys. Aim for a legal memo that happens to be interactive: calm, dense, and typographic. Avoid the generic AI-product look (purple gradients, glassy cards, sparkle icons, emoji) and the generic dashboard look (dark rails, saturated pills, tinted tiles with watermark icons).

- Warm paper background, ivory surfaces, ink text, one ink-blue accent used only for interactive elements
- Semantic colors for status only: red for overdue or passed, amber for due soon and low confidence, green for confirmed. "Not answered by the file" is neutral, not amber
- A serif for the client's name and the brief's narrative, a sans-serif for interface text and numbers; tabular figures for money and dates
- Hairline rules over shadows; 8px radius at most; no cards inside cards; panel headings carry no icon
- A light rail, 15rem, divided from the page by a hairline
- Icons from lucide, used sparingly
- Contrast: text at least 4.5:1, and borders, tracks and focus rings at least 3:1, on every surface including the soft status tints. The ratios sit in a comment beside the tokens in `index.css`

Define colors, type sizes, and spacing as Tailwind theme tokens in one place before building components.

**Margin citations (D38).** A sentence of the brief, or a line of What happened, is one row: the text on the left and its chips in a right-hand gutter (14rem), aligned to the first line. The text reads uninterrupted and each sentence keeps its own chips (D3). Below about 40rem of width the chips drop under the text. A figure marked by the draft checker keeps its own chip inline, since it cites the file's value, not the sentence.

## Firm view: `/matters/:id`

Every view shares the identity header and the rail. The Overview is the 90-second read; For Attorney is the working view.

```
+----------+------------------------------------------------------------------+
| Rail     | Cases / Client / Overview                                        |
| (light)  | [photo] Client name (serif h1)                                   |
|          |   Clio description - Matter no. - incident date, age ago  [src]  |
| Overview |   Stage track (1)(2)(3)(4)(5)  Step 2 of 5: Treating      [src]  |
| For Atty +------------------------------------------------------------------+
| Provider | THE BOTTOM LINE  headline, serif                     | [src][src]|
| Documents| WHAT HAPPENED    the incident account                | [src]     |
| Calls    |   Injuries       up to three                         | [src]     |
|          |   Liability      the leading liability fact          | [src]     |
|          | NOW   Next step | Statute | Last client contact | counts         |
| Viewing  | MONEY Case value | Coverage | Medical specials | Firm spend      |
| as       +----------------------------------------------- end of screen ----+
|          | WHERE IT STANDS  the brief's sentences, one per row  | [src]     |
|          |   Not answered by the file                                       |
|          | THE STORY SO FAR  key events, oldest first, numbered | [src]     |
|          | SINCE YOU LAST OPENED  at most five rows                         |
|          | Synced from Clio at 10:42 - Digest cost $0.00 - [Re-sync]        |
+----------+------------------------------------------------------------------+
```

### Components

- **MatterIdentity.** Rendered by `MatterShell` in every state, so each page has one h1. A breadcrumb whose last item is the view (`aria-current`, not a heading); the client photo from the Clio contact avatar, falling back to initials; the client's name as a serif h1; one case line of the Clio description, the matter number, and the incident date with its age and chip. Nothing without a source: no responsible attorney, no practice area. Sets `document.title` to "view - client - Clarity".
- **StageTrack.** The stage, shown once on every view: five steps, the current one marked, "Step N of 5: Label" in text, an "inferred" marker and a chip. Settled and closed fill the track.
- **BottomLine.** The brief headline in large serif, as a margin-cited row.
- **WhatHappened.** The incident account (`incident_account`: a model fact on the incident day, never the Clio field), up to three injuries with treating providers first, and the leading liability fact. Each a margin-cited row; "Not found in file" when absent.
- **NowStrip.** Cells divided by hairlines: the next step (the first overdue item, else the first task, else the first deadline that is not the statute), the statute with a countdown in words (amber within 90 days, red once passed), the last client contact (words as well as amber after 30 days), and the overdue, upcoming and waiting counts linking to For Attorney.
- **Money row.** The four KPI tiles in one row. Each shows the value, a one-line basis, and a source chip. When two sources disagree, show both values with a warning marker. When nothing supports the KPI, show "Not found in file".
- **WhereItStands.** The brief's sentences, one margin-cited row each, then "Not answered by the file" from `open_questions` as a neutral list.
- **KeyEvents.** About ten key events from `/key-events`: the incident pinned, at most three per kind, oldest first, numbered. Each row shows the date, its lane (Case, Treatment, Negotiation) as a dot and a word, the title, and its chip. "Full timeline" opens For Attorney with the timeline selected.
- **ChangesSince.** Facts newer than the user's last visit, with the date of that visit in the heading. At most five rows, then "and N more". Hidden when there is nothing new; one line on a first visit.
- **For Attorney.** The action board as a table (title, due, owner, status, chip), What matters (Top 10 or the full timeline, chosen in the URL), injuries, and providers with Share.
- **SourceChip.** A small pill showing the source type and, for documents, the page number. A dashed outline marks low confidence. In a margin-cited row the chip is described by its sentence, so two "Email" chips differ.
- **Footer.** Last sync time, digest cost, and a re-sync button, announced as a status when they change. This makes the live read from Clio visible to the screeners.

## Source drawer

A right-side panel that opens over the page from any chip.

- Header: source type, title, date, author or sender
- Notes and emails: the full text with the quote highlighted and scrolled into view
- Documents: the page image at readable width, the page number, previous and next page controls, the quote in a callout above the image, and the page's text under it as its text alternative
- When the fact has corroborating sources, list them as tabs
- Escape and click-outside close it, and focus returns to the chip that opened it; the URL carries `?fact=ID` so a view can be linked

## Share composer

A full-height dialog with two panes.

- Left: the provider's name, section toggles from the visibility table in `docs/architecture.md` (with the off-by-default ones visibly off), a list of included items with a hide control on each, a note field, and an expiry choice.
- Right: a live preview rendered with the same components as the provider view, fed by `/api/shares/{id}/preview`.
- Footer: Create link, then Copy link. A line under the toggles states what is never shared: case value, strategy, negotiations, and internal notes.

## Provider view: `/p/:token`

A single narrow column, readable by office staff with no training.

```
+--------------------------------------------------+
| Firm name                       Shared on date   |
| Patient: Client name                             |
+--------------------------------------------------+
| CASE STATUS                                      |
| Intake > Treating > Demand > Negotiation > ...   |
| Active - last movement on date                   |
+--------------------------------------------------+
| COVERAGE                                         |
| Confirmed / Not yet confirmed                    |
+--------------------------------------------------+
| WHAT THE FIRM NEEDS FROM YOUR OFFICE             |
|  - request, date requested                       |
+--------------------------------------------------+
| YOUR BILLS AND RECORDS ON FILE                   |
|  date  description  amount            [view]     |
+--------------------------------------------------+
| RECENT UPDATES                                   |
|  date  neutral status label                      |
+--------------------------------------------------+
| Note from the firm                               |
+--------------------------------------------------+
```

- Sections whose setting is off are absent, with no placeholder.
- An expired or revoked link shows a plain message and nothing else.
- No navigation to the firm view, and no client-side trace of hidden data.

## States

Every data component handles loading (skeleton, not spinner), empty (one plain sentence), and error (what failed and a retry). A matter that has been synced but not digested shows the header and a prompt to run the digest.

## Out of scope for the UI

Login screens, settings pages, dark mode, a separate mobile design (reflow is required, see principle 6), animations beyond the drawer transition (none under `prefers-reduced-motion`), and any chat input.
