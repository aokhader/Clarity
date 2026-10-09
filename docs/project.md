# Project overview

## What it is

A dashboard over one Clio Manage matter. It reads the whole case file (contacts, custom fields, notes, emails, tasks, calendar, expenses, and documents including scanned PDFs), digests it once into sourced facts, and renders two views from those facts:

- **Firm view:** gets an attorney, paralegal, or case manager up to speed in 90 seconds, then lets them dig.
- **Provider view:** shows a treating medical provider where the case stands and what the firm needs from them, without exposing the rest of the file.

## The problem, from the hackathon brief

Personal-injury cases run for years. Case management systems capture everything, but answering "what's been happening on this case?" still means reading every tab or asking a colleague. Medical providers treat the client on a lien (they are paid from the settlement), so they are betting on the case too, yet they cannot see where it stands or whether there is insurance coverage behind it. Both sides fall back to email.

The brief is explicit that this is not a chat product: "the point is a visual digestion of everything already in the case, so the attorney and the providers get up to speed without having to know what to ask."

It is equally explicit that existing dashboards fail because they show counts and lists and leave the story to be assembled by hand. A grid of KPI tiles over tab links is the thing we are replacing.

## Users

| User | Context | What they need |
|---|---|---|
| Attorney | Opens a matter between other work, often after weeks away | The story, what changed, case value and coverage, proof for every claim |
| Paralegal or case manager | Works the file daily | What is overdue, what is coming, what is waiting on someone else |
| Provider office staff | Outside the firm, treating on lien | Is the case alive, is there coverage, what does the firm need from us |

## Goals

1. An attorney who has never seen the matter can state its status, value, coverage, injuries, and next deadline after 90 seconds on the firm view.
2. Every date, amount, and claim on screen opens its source in one click.
3. A provider can answer their three questions (alive, coverage, what do you need from me) without emailing the firm.
4. The attorney controls exactly what each provider sees and can tell whether it was opened.
5. The pipeline runs on any matter ID, costs a known amount per case, and does not re-digest on every open.

## Non-goals

- A chat interface as the primary surface (the Ask panel of D49 is a secondary tool; the Overview stays the first screen)
- Writing anything back to Clio
- Real authentication, multi-firm tenancy, or mobile layouts
- Sending email or push notifications (a status feed on the provider page stands in for "tell me when the case moves")
- Deployment

## User flows

**1. Get up to speed (firm).** Open the matter. The first screen names the client and the case, gives the bottom line, says what happened (the incident, the injuries, liability), and where the case is now (stage, next step, statute, last client contact, money), each line with its sources in the margin. One scroll down: the key events in order, the suit's filings and answer among them, and where it stands in full, including where the litigation stands (D38, D41, D43).

**2. Catch up (firm).** A "Since you last opened" block lists what changed since this user's last visit. Leaving the page records the visit.

**3. Trace a fact (firm).** Click any chip, date, or amount. A drawer opens with the source note, email, or PDF page, with the supporting quote highlighted.

**4. Work the file (firm).** The action board on For Attorney is a table of overdue and upcoming items and open requests. The Overview's Deadlines and follow-ups row counts them and gives the days since anyone last spoke to the client.

**5. Share with a provider (firm).** Pick a provider from the providers panel. Preview exactly what they will see. Toggle sections, hide individual items, add a note, set an expiry, and copy a link.

**6. Check the case (provider).** Open the link. See a status tracker, whether the case is active, whether coverage is confirmed, what the firm needs from this office, this office's bills and records on file, and the case's moves between stages (D41).

**8. Check a message before sending it (firm).** Write an update to a provider. Each amount and date is checked against the file and the link. A sentence that would disclose an internal figure is locked as "Don't send" (D2).

**9. Call and keep notes (firm).** The Calls view lists who to call next. After the other party's consent is confirmed, the browser transcribes the attorney's side, and the notes that come back each quote the transcript (D8).

**7. Check engagement (firm).** The providers panel shows whether each share was opened and when.

## Scope tiers

Build in this order. When time runs short, cut from the bottom.

**Must (the demo fails without these)**
- Clio sync for the matter by ID
- Fact store with sources
- Firm view: identity header, bottom line, what happened, the now strip and money row, the brief, key events, action board
- Source drawer with click-through to the note, email, or PDF page
- Scanned-PDF extraction with page-level citations
- Provider view behind a share link, filtered on the server

**Should**
- "Since you last opened" block
- Share composer with preview, section toggles, and per-item hide
- Share opened tracking
- Injuries list from the scans
- Verification flags where sources disagree
- Digest cost and "synced from Clio at" indicator

**Cut first**
- Full timeline filters and search
- Share expiry and revoke UI
- Treatment-activity signal on the provider view
- Client photo beyond initials fallback
- Any deployment

## What users asked for, mapped to features

| Request in the brief | Feature |
|---|---|
| "Get me up to speed... without me having to ask anyone." | Brief |
| "What changed since I last opened this matter?" | Since you last opened |
| "Out of three hundred entries, show me the ten that matter." | Ranked feed by significance |
| "Sometimes two minutes. Sometimes I need to dig into everything." | Ranked feed with a full-timeline toggle |
| "If a date is on screen, I need to see where it came from." | Source chips and drawer |
| "Somewhere in a 200-page scan are my client's primary injuries." | Per-page extraction, injuries list |
| "When did anyone last actually talk to the client?" | Last client contact indicator |
| "Don't digest the whole case with AI again every time." | Cached, incremental digest |
| "What's overdue, what's coming, and what's waiting on someone else?" | Action board |
| "What is the case worth, and what coverage sits behind it." | KPI strip |
| "How much has the firm already spent on this case?" | Firm spend KPI from expenses |
| "What did we share with this provider, and has anyone opened it?" | Share record and opened tracking |
| "Let me adjust what the provider sees before I send it." | Share composer |
| "Is there coverage behind the case?" / "Is this case even still alive?" | Provider view status and coverage |
| "What does the firm need from my office right now?" | Provider view requests list |

The brief calls this list "a menu, not a spec. Build the ones you believe in, and build them well." Depth on fewer features beats a thin pass over all of them.

## The sharing line

From the brief: share status changes, bills, and records. Do not share case strategy or anything confidential that is not relevant to the provider. Attorneys differ on where the line sits, so the product ships a conservative default and lets the attorney adjust per share. The exact rules are in `docs/architecture.md` under visibility.

## How we are judged

- **4:00 PM:** Swans screens every build from the repository. Top 7 advance. This stage is won in the code.
- **5:00 PM:** Top 7 get 4 minutes each to pitch their video to the judges. This stage is won on stage.
- **~7:00 PM:** Top 3 are shown on the main stage.

Implication for every decision: a feature that is real and sourced on Sapini beats a prettier feature that is mocked.
