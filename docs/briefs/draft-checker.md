# Brief: the draft checker for provider updates (R0)

**Question:** how should Clarity check a provider status-update draft, sentence by sentence, against the fact store? What does the code already give us, how do other tools show inline checks, and how do we parse amounts and dates with the standard library only?
**Asked by:** the lead, for backend (B1) and ui-builder (U4), under D2. Written by the researcher on 2026-10-07.

Tags: **[docs]** gives the file or URL the claim comes from. **[unverified]** marks a claim not confirmed from a source. **[design]** marks a recommendation from this brief, not a fact.

## 1. Clarity today

### Where the draft text lives
- No editable draft exists yet. "Send update" (`SendUpdateMenu.tsx`, rendered by `ProviderRow.tsx`) fetches `GET /api/shares/{id}/preview`. It builds a message in the browser with `providerUpdateText(payload, url)` and passes it straight to a `mailto:` link, an `sms:` link, or the clipboard. Nobody edits the text, and nothing checks it. **[docs]** `frontend/src/components/share/SendUpdateMenu.tsx`, `providerUpdateText.ts`
- `providerUpdateText` returns `{subject, body, short}`. The body is built only from `ProviderPayload`, one line per item, in the form `- {formatDate(on)}: {label} ({formatMoney(amount)})`. **[docs]** `providerUpdateText.ts:20-26`
- The only text an attorney writes that reaches a provider is the share's **`note`**. It is a `<textarea>` in `ShareComposerForm.tsx`, debounced by 400 ms into `POST /api/matters/{id}/shares/preview`, stored as `Share.note`, and served verbatim as `ProviderPayload.note`. Nothing checks it today. **[docs]** `ShareComposerForm.tsx:35-50,88-99`, `services/provider_view.py:228`
- Formats in the generated text: money is `$2,480` when the cents are zero and `$2,480.50` otherwise. Dates are `Mar 6, 2026`, and the treatment month is `March 2026`. **[docs]** `frontend/src/lib/format.ts:12-59`

### Fact kinds that carry amounts and dates
Every fact has `event_date: date | None`, `title`, `quote`, `page_no`, `source_id` and `provider_contact_id`. **[docs]** `backend/app/models.py:177-211`. Amounts are integer cents in `value_json`. **[docs]** `backend/app/schemas.py:55-203`

| Kind(s) | Amount field(s) | Extra date field | Shareable under |
|---|---|---|---|
| `medical_bill`, `lien` | `amount_cents`, `balance_cents` | - | `own_bills` (own provider only) |
| `policy_limit` | `amount_cents` (+ `per`) | - | `coverage_limits` (off by default) |
| `case_value` | `low_cents`, `high_cents` | - | never |
| `demand`, `offer`, `settlement` | `amount_cents` | - | never |
| `expense` | `amount_cents` | - | never |
| `medical_specials` | `amount_cents` | - | never |
| `task` | - | `due_at` (datetime) | `requests` (own provider, `status == "open"`) |
| `deadline` | - | `due_at` (datetime) | never |
| any kind | `alt_values[].amount_cents` | `alt_values[].on` | (a disagreeing read; never in the payload) |

Dated kinds that a share can release: `case_stage`, `status_change`, `records_received`, `record_request`, `treatment_visit`, and the bills above. **[docs]** `services/visibility.py:26-34`

### How share settings decide what a provider sees
- Default-deny. A fact is released only if all of these hold: an enabled setting names its kind; its `provider_contact_id` equals the share's provider (for `own_bills`, `own_records` and `requests`); `visibility == shareable` and `mentions_strategy` is false; it is not in `hidden_fact_ids_json`; and the share is neither expired nor revoked. **[docs]** `services/visibility.py:1-12,74-119`
- Default settings: `case_stage`, `coverage_exists`, `own_bills`, `own_records` and `requests` are on; `coverage_limits` and `treatment_activity` are off. **[docs]** `schemas.py:427-436`
- `requests` releases only facts whose `status == "open"`. `coverage_exists` releases a boolean, never a carrier or an amount. `treatment_activity` releases only a `YYYY-MM` month. **[docs]** `visibility.py:80-82`, `provider_view.py:123-148,202-206`
- The payload adds values that are **derived, not facts**: `status.last_movement_on` (the latest stage-fact date), `bills_total.amount_cents` (`count_bills`, medical bills only, each charge counted once), `shared_on`, `expires_on`, and `last_visit_month`. **[docs]** `provider_view.py:91-109,189-195,209-241`
- **Trap:** the generated email's "N bills, $X in total" adds up *every* `bills` item, liens included (`totalCents(bills)`). `bills_total` counts `medical_bill` only. When a lien carries an amount, the app's own text disagrees with the provider page. **[docs]** `providerUpdateText.ts:28-30,82` vs `services/bills.py:91-96`
- `ProviderItemOut` carries `fact_id` (bills, records, requests, limits). `ProviderUpdateOut` and `ProviderStatusOut` do not. **[docs]** `schemas.py:496-530`

## 2. How other tools present inline checks

- **Grammarly:** coloured underlines by category: red for correctness (spelling, punctuation, grammar), blue for clarity, green for engagement, purple for delivery (tone). **[docs]** https://www.grammarly.com/blog/product/better-writing-with-grammarly/. You click an underline to get a card, click the suggestion to accept it, or dismiss it. **[unverified]**: the fetched page does not describe these interactions.
- **Microsoft Editor (Word):** red squiggle for spelling, double blue underline for grammar, dotted purple for refinements. Right-clicking the underline shows the suggestion, with "Ignore Once" and "Don't check for this issue". **[docs]** https://support.microsoft.com/en-us/topic/0f43bf32-ccde-40c5-b16a-c6a282c0d251
- **Clearbrief (legal, Word add-in):** checks each cited sentence against the cited record document and gives a colour-coded score for how well the source supports it. It suggests other places in the record and hyperlinks each citation to its source. **[docs]** https://www.lawnext.com/2021/03/new-clearbrief-finds-the-best-evidence-to-strengthen-your-legal-writing.html, https://www.geekwire.com/2021/legal-writing-startup-using-ai-spot-misrepresentations-litigation-docs/
- **Westlaw Quick Check Quotation Analysis:** a redline-style report of missing, added or changed words between a brief's quote and the source. **[docs]** https://legal.thomsonreuters.com/en/c/quick-check-quotation-analysis
- **Accessibility:** colour cannot be the only signal (WCAG 2.1 SC 1.4.1). **[docs]** https://www.w3.org/WAI/WCAG21/Understanding/use-of-color.html

**What this means for Clarity [design]:**
- Underline the *span* (the amount or date), not the whole sentence. Put a verdict badge with an icon and a word in the sentence's margin.
- Clicking the span opens a popover with the source chip and, for "differs", a **"Use the file's value"** button that replaces only that span.
- "Don't send" gets a lock icon and the danger colour, and offers **"Remove sentence"**.

## 3. A check algorithm [design]

1. **Split** the text into lines, then split each line into sentences with `re.split(r"(?<=[.!?])\s+(?=[A-Z\-])", line)`. The lookahead stops `$1,234.56` and `Mar. 6` from splitting. Keep each unit's character offsets.
2. **Extract** amount and date mentions with spans (section 4).
3. **Allowed set:** every amount and date in `provider_payload(session, share, now)`, walked field by field: items, the limits, `bills_total`, the sum of the `bills` amounts (because of the trap above), `last_movement_on`, `shared_on`, `expires_on`, and the month. Build it from the payload the link serves, not from a new query, so "supported" means "the link already shows it".
4. **Internal set:** every amount and date (including `alt_values` and `due_at`) on `renderable_facts(matter_id)` that is not in the allowed set: case value, negotiations, expenses, specials, another provider's bills, hidden facts, and limits while `coverage_limits` is off.
5. **Verdict per mention:**
   - `supported` if it is in the allowed set (chip: that item's `fact_id`).
   - `dont_send` if it is in the internal set only.
   - `differs` if one allowed value is a clear candidate (the sentence contains that item's `label`, or a single same-type value is near it) and the mention does not equal it. Return the file's value and its chip.
   - `not_in_file` otherwise.
6. **Verdict per sentence:** the worst of its mentions, in the order `dont_send` > `differs` > `not_in_file` > `supported`. A sentence with no amount or date is `unchecked`; never call it supported.
7. **Where it runs:** a firm route on the server, with no model call (rule 5). A firm user may see internal facts, so the response may carry a `FactRef` for a `dont_send` match. It still must not echo the internal value into anything the provider receives.

## 4. Parsing with the standard library only

Modules: `re`, `decimal.Decimal`, `datetime.date`. No new dependency is needed. **[docs]** https://docs.python.org/3/library/decimal.html, https://docs.python.org/3/library/datetime.html

**Amounts.** Return integer cents plus a precision, so that "12k" is compared at its own precision.
```python
AMOUNT = re.compile(r"(?:\$|\bUSD\s?)\s?(?P<num>\d{1,3}(?:,\d{3})+|\d+)(?:\.(?P<frac>\d{1,2}))?"
                    r"\s?(?P<suf>k|m|thousand|million)?\b", re.I)
WORDS = re.compile(r"\b(?P<words>(?:(?:zero|one|two|...|ninety|hundred|thousand|million|and)[\s-]+)+)dollars\b", re.I)
```
- `Decimal(num.replace(",", ""))`, plus the `frac` part, times the suffix multiplier, times 100, then `int(...)`. Never `float`, which cannot represent most cents exactly. **[docs]** https://docs.python.org/3/tutorial/floatingpoint.html
- Words ("twelve thousand five hundred dollars"): the standard library has no word-to-number parser **[unverified]**, so write about 20 lines. Keep a `current` and a `total`: units and tens add to `current`; `hundred` multiplies `current` by 100; `thousand` and `million` add `current * scale` to `total` and reset `current`; skip "and".
- Precision: "$12,345.67" is exact to the cent; "$12,345" to the dollar; "12k" to ±$500; "12.3k" to ±$50. A fact matches if it rounds to the written value at that precision.
- Read a number as an amount only if it carries `$`, `USD`, "dollars", or a `k`/`m` suffix after `$`. A bare `3`, `2026` or a phone number is not money.

**Dates.** Use a month table rather than `strptime("%b")`:
- `%b` and `%B` depend on the locale. **[docs]** https://docs.python.org/3/library/datetime.html#strftime-and-strptime-behavior
- "Sept" is not the `%b` abbreviation **[unverified]**.
```python
MONTHS = {"jan": 1, "january": 1, ..., "sep": 9, "sept": 9, "september": 9, ...}
NAMED = re.compile(r"\b(?P<mon>[A-Za-z]{3,9})\.?\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(?P<year>\d{4}))?\b")
DAY_FIRST = re.compile(r"\b(?P<day>\d{1,2})(?:st|nd|rd|th)?\s+(?P<mon>[A-Za-z]{3,9})\.?,?\s+(?P<year>\d{4})\b")
NUMERIC = re.compile(r"\b(?P<m>\d{1,2})/(?P<d>\d{1,2})/(?P<y>\d{4}|\d{2})\b")   # US month-first
ISO = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")                                   # date.fromisoformat
MONTH_YEAR = re.compile(r"\b(?P<mon>[A-Za-z]{3,9})\s+(?P<year>\d{4})\b")      # "March 2026" -> a month
```
- Build each date with `date(y, m, d)` inside `try/except ValueError`, since "Feb 30" is a mention you cannot check. Drop a matched word that is not in `MONTHS` (for example "Policy 2026").
- Two-digit years: follow the POSIX rule that `%y` uses (69-99 become 19xx, 00-68 become 20xx). **[docs]** https://docs.python.org/3/library/time.html
- A date with no year: never call `strptime` on a format with a day and no year. Recent Python versions warn about this, and it may become an error from 3.15. **[docs]** https://docs.python.org/3/library/datetime.html (`date.strptime`). Match the month and day against the allowed set: a unique hit counts as that date, anything else is `not_in_file`.
- Since 3.11, `date.fromisoformat` also accepts `20191204` and `2021-W01-1`. Use it only for the `ISO` regex match. **[docs]** same page

## Rules for the builders
1. Run the check on the server (firm route, POST with the text). No model call, and no new dependency.
2. Build "supported" from `provider_payload()` output plus derived values. Never build it from a new query that bypasses `visible_facts_for_share`.
3. "Don't send" means the value matches only `renderable_facts(matter_id)` outside the payload. Report the `FactRef`, and never put the internal value into the provider text or payload.
4. Money is `int` cents through `Decimal`, never `float`. Bare numbers without `$`, `USD` or "dollars" are not amounts.
5. Compare at the written precision ("12k" is ±$500). The generated text uses `formatMoney`, so it matches to the cent.
6. Sentence verdict = worst mention; no amount or date gives `unchecked`, never `supported`.
7. Add `bills_total` *and* the plain sum of the `bills` amounts to the allowed set, or ask ui-builder to make `providerUpdateText` use `bills_total` (the lien trap in section 1).
8. Check the share `note` too: it is the only free text that reaches the provider unchecked today.
9. UI: underline the span, with an icon and a word (not colour alone). "Use the file's value" replaces only the span. "Don't send" disables Email, Text and Copy until the sentence is removed; overriding the lock is a Manager call.
10. Tests use the synthetic fixture: one fact per verdict, a lien total, a hidden fact, a limit with `coverage_limits` off, and "12k", "twelve thousand dollars", "3/6/26" and "Sept 6".
