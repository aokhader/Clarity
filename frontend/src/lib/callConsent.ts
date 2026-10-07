/**
 * The consent wording for a transcribed call: what the attorney reads to everyone on the
 * call before transcription starts (D27). It is sent to the server as `consent_text` and
 * stored with the call, so a change here is a new version of what was agreed to. It names
 * both services the words go to, and does not name the notes vendor, which `.env` sets and
 * can change. This is a design choice, not legal advice.
 */
export const CONSENT_TEXT =
  "Before we start: I'd like my computer to transcribe this call so I can keep accurate notes. " +
  "My computer's microphone picks up what is said here, which can include your voice if I'm on speakerphone. " +
  "Chrome sends that audio to Google's speech service to turn it into text, and the text then goes to an " +
  'AI service that writes my notes. Everyone on the call has to agree before I start. Is that all right with you?'
