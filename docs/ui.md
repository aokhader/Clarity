# UI

## Principles

1. **A brief, not a dashboard of tiles.** The first thing on screen is the story of the case in sentences. The brief says existing tools fail because they show "counts and lists" and leave the story to be assembled by hand.
2. **Everything is clickable evidence.** Every date, amount, and claim is a chip that opens its source. Text with no source is limited to labels and headings.
3. **Two depths.** The default view fits 90 seconds. One toggle opens the full timeline.
4. **No chat box.** The user should not need to know what to ask.
5. **Honest uncertainty.** Low-confidence facts carry a visible marker. Disagreeing sources show both values. Missing data says "Not found in file".
6. **Built to be filmed.** The clip is 90 seconds and the judges see it on a projector. Use large type for the KPI strip and the brief, strong contrast, and a 1440 by 900 desktop layout. Mobile is out of scope.

## Visual direction

The audience is trial attorneys. Aim for a legal document that happens to be interactive: calm, dense, and typographic. Avoid the generic AI-product look (purple gradients, glassy cards, sparkle icons, emoji).

- Background off-white, surfaces white, text near-black, one accent color used only for interactive elements
- Semantic colors for status only: red for overdue, amber for due soon and low confidence, green for confirmed
- A serif for the brief's narrative text and a sans-serif for interface text and numbers; tabular figures for money and dates
- Thin borders over shadows; 8px radius at most
- Icons from lucide, used sparingly

Define colors, type sizes, and spacing as Tailwind theme tokens in one place before building components.

## Firm view: `/matters/:id`

```
+----------------------------------------------------------------------------+
| [photo] Client name   Matter description        [Stage pill]   [User v]    |
|         Date of incident - case age - Last client contact: N days ago      |
+----------------------------------------------------------------------------+
| Case value      | Coverage        | Medical specials  | Firm spend         |
| $ range  [src]  | $ limit  [src]  | $ total  [src]    | $ total  [src]     |
+----------------------------------------------------------------------------+
| BRIEF                                        | ACTION BOARD                |
| Headline sentence.                           |  Overdue (n)                |
| Five to eight sentences, each ending in      |  Upcoming (n)               |
| one or more source chips.                    |  Waiting on others (n)      |
|                                              +-----------------------------+
| SINCE YOU LAST OPENED (date)                 | INJURIES                    |
|  - changed item  [src]                       |  - injury  [src p.12]       |
|                                              +-----------------------------+
| WHAT MATTERS   [Top 10 | Full timeline]      | PROVIDERS                   |
|  date  kind  title                    [src]  |  Name - role                |
|  date  kind  title                    [src]  |  Billed $ - records status  |
|  ...                                         |  Shared, opened 2h ago      |
|                                              |  [Share]                    |
+----------------------------------------------------------------------------+
| Synced from Clio at 10:42 - Digest cost $0.00 - [Re-sync]                  |
+----------------------------------------------------------------------------+
```

### Components

- **MatterHeader.** Client photo from the Clio contact avatar, falling back to initials. Stage pill; when the stage is inferred, the pill says so and has a source chip.
- **KpiStrip.** Four tiles. Each shows the value, a one-line basis, and a source chip. When two sources disagree, show both values with a warning marker. When nothing supports the KPI, show "Not found in file".
- **Brief.** Headline in larger type, then the sentences. Chips sit at the end of each sentence. Below, a short "Not answered by the file" list from `open_questions`.
- **ChangesSince.** Lists facts newer than the user's last visit, with the date of that visit in the heading. Hidden when there is nothing new. Collapses to a single line when the user has never opened the matter.
- **RankedFeed.** Top 10 facts by significance: date, kind badge, title, chip. A toggle switches to the full timeline grouped by month, with kind filters and text search.
- **ActionBoard.** Three groups. Each item shows the title, due date, assignee, and a chip. "Waiting on others" includes open record requests to providers.
- **InjuriesList.** Injuries and diagnoses with body part and the page they came from.
- **ProvidersPanel.** One row per medical provider: name, role, billed total, records received or outstanding, and share status (not shared, shared, opened with relative time). A Share button opens the composer.
- **SourceChip.** A small pill showing the source type and, for documents, the page number. A dashed outline marks low confidence.
- **Footer.** Last sync time, digest cost, and a re-sync button. This makes the live read from Clio visible to the screeners.

## Source drawer

A right-side panel that opens over the page from any chip.

- Header: source type, title, date, author or sender
- Notes and emails: the full text with the quote highlighted and scrolled into view
- Documents: the page image at readable width, the page number, previous and next page controls, and the quote in a callout above the image
- When the fact has corroborating sources, list them as tabs
- Escape and click-outside close it; the URL carries `?fact=ID` so a view can be linked

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

Login screens, settings pages, dark mode, mobile layouts, animations beyond the drawer transition, and any chat input.
