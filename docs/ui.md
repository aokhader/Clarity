# UI

## Principles

1. **A brief, not a dashboard of tiles.** The first thing on screen is the story of the case in sentences. The brief says existing tools fail because they show "counts and lists" and leave the story to be assembled by hand.
2. **Everything is clickable evidence.** Every date, amount, and claim is a chip that opens its source. Text with no source is limited to labels and headings.
3. **Two depths.** The default view fits 90 seconds. One toggle opens the full timeline.
4. **No chat box.** The user should not need to know what to ask.
5. **Honest uncertainty.** Low-confidence facts carry a visible marker. Disagreeing sources show both values. Missing data says "Not found in file".
6. **Built to be filmed.** The clip is 90 seconds and the judges see it on a projector. Use large type for the brief's headline, strong contrast, and a 1440 by 900 desktop layout. There is no separate mobile design, but every view reflows down to 320 CSS px so it survives 200% and 400% zoom (WCAG 1.4.10).
7. **The 90-second test (D38).** The Overview's first screen at 1440 by 900 answers at least 9 of these, and one scroll answers all 12: what kind of case; when it happened; what happened; the injuries; whether the client is still treating; the stage; value against coverage; the statute; what is overdue, next or waited on; the last client contact; what changed lately; what has happened so far, in order.

## Visual direction

The audience is trial attorneys. Aim for a legal memo that happens to be interactive: calm, dense, and typographic. Avoid the generic AI-product look (purple gradients, glassy cards, sparkle icons, emoji) and the generic dashboard look (dark rails, saturated pills, tinted tiles with watermark icons).

- Warm paper background, ivory surfaces, ink text, one ink-blue accent used only for interactive elements
- Semantic colors for status only: red for overdue or passed, amber for due soon and low confidence, green for confirmed. "Not answered by the file" is neutral, not amber
- A serif for display lines only, the client's name and the brief's headline; one sans-serif for everything meant to be read, the brief's sentences included (16px, relaxed leading), and for interface text and numbers (D44); tabular figures for money and dates
- Hairline rules over shadows; 8px radius at most; no cards inside cards; panel headings carry no icon
- A light rail, 15rem, divided from the page by a hairline
- Icons from lucide, used sparingly
- Contrast: text at least 4.5:1, and borders, tracks and focus rings at least 3:1, on every surface including the soft status tints. The ratios sit in a comment beside the tokens in `index.css`

Define colors, type sizes, and spacing as Tailwind theme tokens in one place before building components.

**Margin citations (D38).** A sentence of the brief, or a line of What happened, is one row: the text on the left and its chips in a right-hand gutter (14rem), aligned to the first line. The text reads uninterrupted and each sentence keeps its own chips (D3). Below about 40rem of width the chips drop under the text. A figure marked by the draft checker keeps its own chip inline, since it cites the file's value, not the sentence.

## Firm view: `/matters/:id`

Every view shares the identity header and the rail. The Overview is the 90-second read; For Attorney is the working view. On the Overview each block is its own card on the paper, 12px apart, so one is told from the next; the cards sit side by side in the page, never inside one another (D46).

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
|          | THE STORY SO FAR  key events, oldest first, numbered | [src]     |
|          |   Also in the file, without a date: Filed [src] - Served [src]   |
|          | SINCE YOU LAST OPENED  at most five rows (hidden if none)        |
|          | WHERE IT STANDS  the brief's sentences, one per row  | [src]     |
|          |   Not answered by the file                                       |
|          | Synced from Clio at 10:42 - Digest cost $0.00 - [Re-sync]        |
+----------+------------------------------------------------------------------+
```

### Components

- **MatterIdentity.** Rendered by `MatterShell` in every state, so each page has one h1. A breadcrumb whose last item is the view (`aria-current`, not a heading); the client photo from the Clio contact avatar, falling back to initials; the client's name as a serif h1; one case line of the Clio description, the matter number, and the incident date with its age and chip. Nothing without a source: no responsible attorney, no practice area. Sets `document.title` to "view - client - Clarity".
- **StageTrack.** The stage, shown once on every view: five steps, the current one marked, "Step N of 5: Label" in text, an "inferred" marker and a chip. Earlier steps are filled but never marked "completed": a case in litigation can still be treating (D40). Settled and closed fill the track.
- **BottomLine.** The brief headline in large serif, as a margin-cited row.
- **WhatHappened.** The incident account (`incident_account`: a model fact on the incident day, never the Clio field), the injuries as one row per body region, most-stated first, up to three, with no injury count (D40), and the two most significant liability facts, so a contested point is not shown as settled. Each a margin-cited row; "Not found in file" when absent.
- **NowStrip.** Cells divided by hairlines: the next step, labelled "Overdue" when it is (the first overdue item, else the first task, else the first deadline that is not the statute), the statute with a countdown in words (amber within 90 days, red once passed, and "Met" in neutral ink when its Clio task is complete), the last client contact (words as well as amber after 30 days), and the overdue, upcoming and open-request counts linking to For Attorney.
- **Money row.** The four KPI tiles in one row. Each shows the value, a one-line basis, and a source chip. When two sources disagree, show both values with a warning marker. When nothing supports the KPI, show "Not found in file".
- **WhereItStands.** The brief's sentences, one margin-cited row each, then "Not answered by the file" from `open_questions` as a neutral list. In litigation, one sentence says where the suit stands: the defenses pleaded and any earlier dismissal or refiling (brief prompt version 5, D43).
- **KeyEvents.** About ten key events from `/key-events`, oldest first and numbered. The rows are chosen in this order:
  - the incident account, pinned;
  - up to three dated court events (`litigation_event`), pinned by type: filed, dismissed, renewed and answered first, then the rest (D41, D43). By score alone they fall below the cutoff, yet the suit is part of what happened;
  - other dated past events, at most three per kind. Deadlines are left out, since they are scheduled, not things that happened.

  Each row shows the date, its lane (Case, Treatment, Negotiation) as a dot and a word, the title, and its chip. Court events are in the Case lane, and a row's extra chips count source records, not pages. "Full timeline" opens For Attorney with the timeline selected.
- **UndatedCourtEvents.** One line under the story, from `/key-events/undated`: "Also in the file, without a date:" and each court event no record dates, named by its type word (Filed, Served, Dismissed and so on) with its chips. It leaves out an event a dated record restates, and is absent when there are none. A court event is never dated by the note that reports it, since a note can be written before or long after the event (D43).
- **ChangesSince.** Facts newer than the user's last visit, with the date of that visit in the heading. At most five rows, then "and N more". Hidden when there is nothing new; one line on a first visit.
- **For Attorney.** The action board as a table (title, due, owner, status, chip), What matters (Top 10 or the full timeline, chosen in the URL), injuries, and providers with Share.
- **SourceChip.** A small pill showing the source type and, for documents, the page number. A dashed outline marks low confidence. In a margin-cited row the chip is described by its sentence, so two "Email" chips differ.
- **Footer.** Last sync time, digest cost, and a re-sync button, announced as a status when they change. This makes the live read from Clio visible to the screeners.

## Source drawer

A right-side panel that opens over the page from any chip.

- Header: the fact, its kind, date and confidence. Under it, the cited quote in a callout, for every source type, so the passage is read before the record (D45). Then one line naming the record (source type, date, author or sender) and its title
- Text records (notes, emails, calendar entries, calls): the full text in the sans at 16px with relaxed leading and about 68 characters to a line, split into its paragraphs; bulleted or numbered lines are real lists and a line's leading "Label:" is bold. The wording is never changed, and the quote is marked where it sits. The drawer opens at the top, so the callout is read first; its "Show in the record" button scrolls to the mark and moves focus there
- Matter and task records: each aspect under a small heading. Short values (dates, money, yes or no) sit in a two-column grid; longer values follow it as labelled paragraphs in their original order (D45)
- Documents: the page image at readable width, the page number, previous and next page controls, and the page's text under it as its text alternative
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
| From your patient's law firm       Shared date   |
| Patient: Client name (serif h1)                  |
| Prepared for Provider name                       |
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
|  Bills total                                     |
|  Bills and liens                                 |
|   date  description  amount           [view]     |
|   date  Lien  description  amount     [view]     |
|  Records                                         |
+--------------------------------------------------+
| RECENT UPDATES                                   |
|  date  Moved to litigation                       |
+--------------------------------------------------+
| Note from the firm                               |
+--------------------------------------------------+
```

- The firm's name is not shown, since no synced record carries it.
- The bills total counts bills only. A lien is listed and labelled "Lien", and a caption says liens are not added to the total (D35).
- Recent updates lists only moves to a named stage, in labels written in code ("Moved to treatment", "Moved to litigation"). The record's own wording for a status never reaches a provider, because it can name what the firm keeps, such as a past dismissal (D41). Court events are internal.
- Sections whose setting is off are absent, with no placeholder.
- An expired or revoked link shows a plain message and nothing else.
- No navigation to the firm view, and no client-side trace of hidden data.

## States

Every data component handles loading (skeleton, not spinner), empty (one plain sentence), and error (what failed and a retry). A matter that has been synced but not digested shows the header and a prompt to run the digest.

## Out of scope for the UI

Login screens, settings pages, dark mode, a separate mobile design (reflow is required, see principle 6), animations beyond the drawer transition (none under `prefers-reduced-motion`), and any chat input.
