/**
 * The consent wording for a transcribed call: what the attorney reads to everyone on the
 * call before transcription starts. It is sent to the server as `consent_text` and stored
 * with the call, so a change here is a new version of what was agreed to. From the R1
 * brief (docs/briefs/calls.md, section 3); this is a design choice, not legal advice.
 */
export const CONSENT_TEXT =
  "Before we start: I'd like my computer to transcribe this call so I can keep accurate notes. " +
  "Only my side is transcribed, from my computer's microphone. Chrome sends that audio to Google's " +
  'speech service to turn it into text. Is that all right with you?'
