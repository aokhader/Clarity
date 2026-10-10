# Brief: Calls, option A (R1)

**Question:** what do the builders need to know to ship Calls (A) (D8)? That is: a `tel:` hand-off, the browser transcribing the attorney's microphone after a logged consent step, and AI notes that cite the transcript. Where are the phone numbers in our synced data?
**Asked by:** the lead, for backend (C-B), pipeline (C-P) and ui-builder (C-U). Written by the researcher on 2026-10-07.

Tags:
- **[docs]**: the file or URL was read.
- **[docs\*]**: known only from a search-result summary; the page was not opened.
- **[unverified]**: not confirmed.
- **[design]**: a recommendation from this brief.

## 1. Browser speech recognition (Web Speech API)

**Support** (MDN browser-compat-data, https://github.com/mdn/browser-compat-data/blob/main/api/SpeechRecognition.json **[docs]**):
- Chrome: `webkitSpeechRecognition` since 33, and unprefixed `SpeechRecognition` since 139.
- Safari: prefixed, since 14.1 (iOS 14.5).
- Firefox: "preview" only. caniuse says "disabled by default" (https://caniuse.com/speech-recognition **[docs]**).
- Edge: the sources disagree. The compat data says it mirrors Chrome; caniuse says it is not supported. Treat Edge as untested and demo in Chrome.

**Settings** (https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition **[docs]**):
- `continuous` defaults to `false`, which ends recognition when the speaker stops talking (https://developer.chrome.com/blog/voice-driven-web-apps-introduction-to-the-web-speech-api **[docs]**).
- `interimResults = true` delivers results that are not final yet (`SpeechRecognitionResult.isFinal === false`).
- `lang` takes a BCP-47 tag (`"en-US"`). It defaults to the page's `<html lang>`, then to the browser's language. A language the browser lacks raises `language-not-supported`.
- Events: `start`, `end`, `result`, `error`, `nomatch`, `audiostart`/`audioend`, `soundstart`/`soundend`, `speechstart`/`speechend`.
- Results carry text and confidence but no timestamps **[unverified]**. Stamp each final result yourself with the milliseconds since the call started **[design]**.

**Errors** (`event.error`, https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognitionErrorEvent/error **[docs]**): `aborted`, `audio-capture`, `language-not-supported`, `network`, `no-speech`, `not-allowed`, `phrases-not-supported`, `service-not-allowed`.

**Session limits and restarting:**
- Chrome ends a `continuous` session on its own, reportedly after about a minute, and after silence (`no-speech`). **[unverified]** Developer reports: https://github.com/WebAudio/web-speech-api/issues/96, https://www.construct.net/en/forum/construct-2/closed-bugs-22/continuous-mode-speech-108443
- The usual fix is to call `start()` again in `onend`. Do not restart after `not-allowed` or `service-not-allowed`, and guard against restart loops. **[docs\*]** (annyang guidance, via search)
- Pattern **[design]**:
  - Keep a `callActive` flag and record the last error.
  - In `onend`, restart after about 250 ms if `callActive` is true and the last error is not one of `not-allowed`, `service-not-allowed`, `audio-capture` or `language-not-supported`. Cap restarts (for example 10 a minute), then show "Transcription stopped. Resume?".
  - `start()` on a running instance throws `InvalidStateError` **[unverified]**, so restart only from `onend`.
  - Interim text pending at `end` is lost. Store finals only.

**Network, where the audio goes, and localhost:**
- On some browsers, like Chrome, recognition uses a server-based engine: "Your audio is sent to a web service for recognition processing, so it won't work offline." The MDN SpeechRecognition page **[docs]**.
  - In Chrome that service is Google's: PLAN.md (D8), and https://wiki.mozilla.org/Web_Speech_API_-_Speech_Recognition contrasts Firefox's anonymising proxy with Chrome **[docs]**.
  - Google's retention of the audio: **[unverified]**.
  - Offline, or with the service blocked, the API fails with `network`.
- Chrome 139 adds on-device recognition, so that "audio and transcribed speech are not sent to a third-party service" (https://developer.chrome.com/blog/new-in-chrome-139 **[docs]**). It is used through `processLocally`, `SpeechRecognition.available()` and `install()` (MDN, compat data **[docs]**). It is experimental and needs a language pack.
  - The exact call signatures: **[unverified]**.
  - Use it only if `available()` reports en-US as ready on the demo machine, and change the consent wording to match.
- `http://localhost` is a secure context (https://developer.mozilla.org/en-US/docs/Web/Security/Secure_Contexts **[docs]**), so the microphone works on `http://localhost:5173`.
  - A LAN address (`http://192.168...`) is not a secure context, so the microphone is blocked there.
  - Over plain HTTP, Chrome asks for permission on every start; over HTTPS it asks once (Chrome blog, 2013 **[docs]**). Whether `localhost` asks again on each restart is **[unverified]**; test it.
- It hears only this microphone. With the call on speaker, the other party may be picked up, or removed by echo cancellation **[unverified]**.
- Whether recognition keeps running when the `tel:` app takes focus is **[unverified]**; test it before the demo.

## 2. `tel:` links

- **Syntax** (RFC 3966, https://www.rfc-editor.org/rfc/rfc3966 **[docs]**): global numbers (`+` and the digits) "SHOULD be used". The allowed visual separators are `-`, `.`, `(` and `)`; spaces are not allowed. Write `tel:+1XXXXXXXXXX` **[design]**.
- **Windows 11:**
  - The app chosen for **TEL** under Settings > Apps > Default apps > link type handles the link (https://learn.microsoft.com/en-us/answers/questions/4007141/phone-link-tel-links **[docs]**).
  - Phone Link supports `tel:`, but one user reports still getting an app chooser after making it the default (same thread **[docs]**).
  - Teams can be the TEL handler once it is installed and signed in (https://kb.uwm.edu/69319 **[docs\*]**).
  - With no handler, Windows asks the user to pick an app **[unverified]**. Chrome first shows its own "Open <app>?" prompt **[unverified]**.
- **macOS:**
  - The Mac calls through the iPhone. Turn on FaceTime > Settings > General > "Calls from iPhone"; a Wi-Fi connection is needed, and the iPhone "must be nearby".
  - Clicking a phone number in Safari starts the call (https://support.apple.com/guide/mac-pro/apd4342f6d6e/2022/mac/13 **[docs]**).
  - In Chrome on a Mac, the link opens FaceTime **[unverified]**.
- The page never learns whether the call connected or ended, so the attorney presses "Start transcribing" and "End call" **[design]**.

## 3. Consent (this is research, not legal advice)

**This section is not legal advice.** A California lawyer should confirm the consent flow before anyone transcribes a real call.

**What the statute says**
- **Penal Code s. 632(a)** covers a person who, "intentionally and without the consent of all parties to a confidential communication, uses an electronic amplifying or recording device to eavesdrop upon or record the confidential communication". (https://california.public.law/codes/ca_penal_code_section_632 **[docs]**) The penalty is a fine up to $2,500 per violation, jail, or both **[docs\*]**.
- **s. 632(c)** defines a confidential communication as one where the circumstances "reasonably indicate that any party ... desires it to be confined to the parties". It excludes circumstances in which the parties "may reasonably expect that the communication may be overheard or recorded". (same page **[docs\*]**)
- **s. 637.2** gives a civil action for $5,000 per violation, or three times actual damages, and actual damages are "not a necessary prerequisite". (https://california.public.law/codes/ca_penal_code_section_637.2 **[docs]**)
- **s. 632.7** requires all-party consent to record a call involving a cellular or cordless phone, whether or not it is confidential. (https://california.public.law/codes/ca_penal_code_section_632.7 **[docs]**)

**Does transcription count as recording?**
- Not settled. *In re Otter.AI Privacy Litigation* (N.D. Cal., No. 5:25-cv-06911-EKL, consolidated in October 2025) alleges that an AI notetaker's recording and transcription violates California's privacy act. (https://www.sally.io/blog/otter-ai-class-action-lawsuit, https://news.bloomberglaw.com/litigation/ai-notetaking-poses-wiretapping-discovery-and-ethical-pitfalls **[docs\*]**)
- **Treat transcription as recording [design].**
- Chrome also sends the audio to a third-party service (section 1), so say so in the consent.

**Wording comparable products use**
- Zoom: "This meeting is being recorded. By staying in this meeting, you consent to being recorded." (https://uis.jhu.edu/zoom/new-setting-recording-disclaimer-enabled **[docs\*]**)
- Otter's notetaker shows each participant a consent pop-up and posts in the meeting chat. (https://support.lanecc.edu/en_US/zoom/otterpilot-captions-in-zoom-meetings **[docs\*]**)

**Clarity's wording [design]**
- Script for the attorney to say: *"Before we start: I'd like my computer to transcribe this call so I can keep accurate notes. The audio is processed by Google's speech service. Is that all right with you?"*
- Checkbox: *"[Contact] agreed to transcription of this call."* With the buttons **Agreed, start transcribing** and **Declined, call without transcription**.
- Log both outcomes: user id, contact id, UTC time, and the version of the wording.

## 4. How comparable tools present call notes

- **Clio Manage phone logs:** they live in the Communications tab and the matter's and contact's subtabs. They link to a matter, contact or user, record From/To, and can carry billable time. (https://help.clio.com/hc/en-au/articles/9125244587675-Phone-Logs **[docs\*]**) In the API they are communications of type `PhoneCommunication`. (`docs/reference/clio-openapi.json:17211-17214` **[docs]**) Clarity must not write them (rule 1).
- **Fathom:** a structured summary, highlights, and action items with timestamps that jump to the moment in the recording. (https://zapier.com/blog/fathom-features/ **[docs\*]**)
- **Jamie:** tasks, decisions and timestamps, from the computer's audio with no meeting bot.
- **VXT (a law-firm phone system):** a transcript after each call, saved to the matter, with summary prompts (action items, bullets) the firm can tune. (https://www.meetjamie.ai/blog/ai-note-takers-for-lawyers **[docs\*]**, for both Jamie and VXT)
- **For Clarity [design]:**
  - Order the notes: summary (up to 3 sentences), then commitments (who, what, by when), dates and amounts mentioned (parsed in code), and follow-ups.
  - Every line gets a chip that opens the transcript with its segment highlighted.
  - Show a banner: "Only your microphone was transcribed."

## 5. Clarity's side: phone numbers in the synced Clio data

- **Where they are:** `sources` rows with `clio_type = 'contact'` and `clio_id` = the Clio contact id as a string. The `raw_json` keys are `id, etag, name, type, title, email_addresses[{address,name}], phone_numbers[{number,name}], addresses[...], custom_field_values[...], avatar, updated_at`. (`backend/app/clio/sync.py:56-65` **[docs]**)
- **Fallback trap:** if Clio rejects that field list, the sync retries with `id,etag,name,type,updated_at` and records `contact_fallback_fields`. Then `phone_numbers` is **absent** (`sync.py:305-328` **[docs]**). Read it with `raw_json.get("phone_numbers") or []`.
- **What the spec allows:** a PhoneNumber has `number` (string), `name` (enum `Work`/`Personal`/`Other`), `primary`, `id`, `etag` and timestamps; the sync requests only `number` and `name`. A Contact also has `primary_phone_number`, which is not synced. (`docs/reference/clio-openapi.json:77014-77053, 72649` **[docs]**)
- **Which contacts are synced:** the matter's relationships plus its client. (`sync.py:211-226` **[docs]**)
- **The real matter, by shape only:** from a byte-level search of `data/app.db`, since this role has no shell for SQL **[docs]**.
  - 15 contact records, all with the full field set.
  - 14 have `phone_numbers: []`; 1 (`type: Person`) has one entry. **No `Company` contact has a number.**
  - 9 have at least one email address.
  - The one number is a display string with parentheses, a space and a hyphen, not E.164.
  - Confirm with `SELECT count(*), sum(json_array_length(raw_json,'$.phone_numbers') > 0) FROM sources WHERE clio_type='contact';`
  - This matches `docs/tracks/c-provider.md:73` ("no synced field holds the provider's email or phone").
- **Code gaps:**
  - `RawContact` parses only `name` and `avatar` (`backend/app/services/clio_records.py:41-43` **[docs]**).
  - The synthetic fixture has no phone numbers (search **[docs]**).
  - The lookup to copy is `shares.contact_name` (`services/shares.py:76-84`).
- **Who to call:**
  - `actions()` puts open tasks whose `waiting_on` is not `None`/`"firm"`, and open record requests, into `waiting_on_others`. Overdue tasks stay in `overdue` even when they are waiting on someone. (`services/matter_queries.py:195-227` **[docs]**)
  - Map each item to a contact:
    - a provider: `Fact.provider_contact_id`;
    - `waiting_on == "client"`: the matter record's `client.id`;
    - the insurer: `FieldMappingContent.contact_roles` (`services/shares.py:59-73`).
- **Last contact:** synced communications have `type` `EmailCommunication` or `PhoneCommunication`, and both occur in the real data. `client_contact` facts cover the client only. (`schemas.py:155-160` **[docs]**)

## Rules for the builders
1. Detect support with `window.SpeechRecognition ?? window.webkitSpeechRecognition`, typed through a small local interface (no `any`). Without it, show "Transcription needs Chrome" and still allow the call.
2. Set `continuous = true`, `interimResults = true` and `lang = "en-US"`. Store only `isFinal` results, as segments `{id, t_ms, text}`; show interim text in grey.
3. Restart in `onend` only while the call is active and the last error is not `not-allowed`, `service-not-allowed`, `audio-capture` or `language-not-supported`. Delay each restart and cap the number.
4. Do not transcribe before consent is logged (user, contact, UTC time, wording version). "Declined" places the call without transcription.
5. The consent wording names the speech service (Chrome is server-based), unless on-device `processLocally` was confirmed for this session.
6. Build `tel:` from digits only: `tel:+1` plus 10 digits. Otherwise render no link. Always show the number with a Copy button.
7. Read numbers with `raw_json.get("phone_numbers") or []`. On the real matter nearly every row has none, so build the "No number in Clio" state first.
8. Never dial a number from the matter in a test (PLAN C-T). Calling the Manager's own phone needs a number typed into Clarity and stored only in our database, which needs the lead's decision.
9. Notes cite a segment id and a quote, checked by `verify.py`. A note that fails is dropped. Call notes are `internal`.
10. Serve on `http://localhost`, not a LAN IP. Before the demo, test the `tel:` hand-off and whether recognition survives the focus change.
