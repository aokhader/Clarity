import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

/**
 * The part of the Web Speech API's recogniser this hook uses. The DOM library types its
 * events but not the recogniser itself, which Chrome still ships as `webkitSpeechRecognition`.
 */
type Recognizer = {
  continuous: boolean
  interimResults: boolean
  lang: string
  start(): void
  stop(): void
  abort(): void
  onresult: ((event: SpeechRecognitionEvent) => void) | null
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null
  onend: (() => void) | null
}
type RecognizerConstructor = new () => Recognizer

function recognizerConstructor(): RecognizerConstructor | null {
  const speech = window as unknown as {
    SpeechRecognition?: RecognizerConstructor
    webkitSpeechRecognition?: RecognizerConstructor
  }
  return speech.SpeechRecognition ?? speech.webkitSpeechRecognition ?? null
}

const LANG = 'en-US'
/** Chrome ends a session on silence and after about a minute, so it is started again. */
const RESTART_DELAY_MS = 250
const RESTART_WINDOW_MS = 60_000
const MAX_RESTARTS_PER_WINDOW = 10

/** Errors a restart cannot fix: the user or the browser has to act first. */
const FATAL_ERRORS: ReadonlySet<SpeechRecognitionErrorCode> = new Set([
  'not-allowed',
  'service-not-allowed',
  'audio-capture',
  'language-not-supported',
])

const PROBLEMS: Partial<Record<SpeechRecognitionErrorCode, string>> = {
  'not-allowed':
    "The microphone is blocked for this site. Allow it from the icon in Chrome's address bar, then press Resume.",
  'service-not-allowed': "This browser does not allow its speech service here, so nothing can be transcribed.",
  'audio-capture': 'No microphone was found. Connect one, then press Resume.',
  'language-not-supported': 'This browser cannot transcribe US English.',
  network: "Chrome could not reach Google's speech service. Check the connection; it keeps trying.",
}
const TOO_MANY_RESTARTS = 'Transcription stopped after restarting too often. Press Resume to continue.'

/** One final result, timed from the moment transcription first started. */
export type TranscriptSegment = { id: number; tMs: number; text: string }

/**
 * idle: not started. listening: transcribing. stopped: ended by the call. paused: stopped
 * after too many restarts, until Resume. blocked: an error only the user can fix.
 */
export type SpeechStatus = 'idle' | 'listening' | 'stopped' | 'paused' | 'blocked'

/**
 * The browser's speech recognition of this computer's microphone, for the length of a
 * call. Only final results are kept; interim text is shown while it settles. Chrome sends
 * the audio to Google's speech service, so start only after consent is logged.
 */
export function useSpeechTranscript() {
  const [Constructor] = useState(recognizerConstructor)
  const [status, setStatus] = useState<SpeechStatus>('idle')
  const [segments, setSegments] = useState<TranscriptSegment[]>([])
  const [interim, setInterim] = useState('')
  const [problem, setProblem] = useState<string | null>(null)

  const recognizer = useRef<Recognizer | null>(null)
  /** The call wants transcription: true from start() until stop(). */
  const active = useRef(false)
  const lastError = useRef<SpeechRecognitionErrorCode | null>(null)
  const restarts = useRef<number[]>([])
  const startedAt = useRef<number | null>(null)
  const nextId = useRef(0)
  const restartTimer = useRef<number | null>(null)
  /** A session is running; its end event is still to come. */
  const running = useRef(false)

  const listen = useCallback((target: Recognizer) => {
    try {
      target.start()
      running.current = true
      setStatus('listening')
    } catch {
      // Already running: its own end event will start it again.
    }
  }, [])

  const recognizerFor = useCallback(
    (Make: RecognizerConstructor): Recognizer => {
      if (recognizer.current) return recognizer.current
      const created = new Make()
      created.continuous = true
      created.interimResults = true
      created.lang = LANG

      created.onresult = (event) => {
        const finals: TranscriptSegment[] = []
        let pending = ''
        for (let index = event.resultIndex; index < event.results.length; index++) {
          const result = event.results[index]
          const text = result[0]?.transcript.trim() ?? ''
          if (text === '') continue
          if (result.isFinal) {
            const tMs = Math.round(performance.now() - (startedAt.current ?? performance.now()))
            finals.push({ id: nextId.current++, tMs, text })
          } else {
            pending = `${pending} ${text}`.trim()
          }
        }
        if (finals.length > 0) setSegments((current) => [...current, ...finals])
        setInterim(pending)
        // Speech is arriving, so any passing network trouble is over.
        lastError.current = null
        setProblem(null)
      }

      created.onerror = (event) => {
        lastError.current = event.error
        const message = PROBLEMS[event.error]
        if (message) setProblem(message)
        if (FATAL_ERRORS.has(event.error)) setStatus('blocked')
      }

      created.onend = () => {
        running.current = false
        // Interim text still pending when a session ends is lost; only finals are kept.
        setInterim('')
        if (!active.current) {
          setStatus('stopped')
          return
        }
        if (lastError.current !== null && FATAL_ERRORS.has(lastError.current)) {
          setStatus('blocked')
          return
        }
        const now = Date.now()
        restarts.current = restarts.current.filter((at) => now - at < RESTART_WINDOW_MS)
        if (restarts.current.length >= MAX_RESTARTS_PER_WINDOW) {
          setStatus('paused')
          setProblem(TOO_MANY_RESTARTS)
          return
        }
        restarts.current.push(now)
        restartTimer.current = window.setTimeout(() => {
          restartTimer.current = null
          if (active.current) listen(created)
        }, RESTART_DELAY_MS)
      }

      recognizer.current = created
      return created
    },
    [listen],
  )

  /** Start, or resume after a pause or a fixed permission, while the call is on. */
  const start = useCallback(() => {
    if (!Constructor) return
    active.current = true
    lastError.current = null
    restarts.current = []
    setProblem(null)
    startedAt.current ??= performance.now()
    listen(recognizerFor(Constructor))
  }, [Constructor, listen, recognizerFor])

  /**
   * The call is over: stop listening, keeping what was transcribed. A running session
   * still delivers its last final results, then reports `stopped` from its end event.
   */
  const stop = useCallback(() => {
    active.current = false
    if (restartTimer.current !== null) window.clearTimeout(restartTimer.current)
    restartTimer.current = null
    if (running.current) recognizer.current?.stop()
    else setStatus('stopped')
  }, [])

  useEffect(
    () => () => {
      active.current = false
      if (restartTimer.current !== null) window.clearTimeout(restartTimer.current)
      recognizer.current?.abort()
      recognizer.current = null
    },
    [],
  )

  /** The transcript so far, one final result per line, as it is saved with the call. */
  const transcript = useMemo(() => segments.map((segment) => segment.text).join('\n'), [segments])

  return { supported: Constructor !== null, status, segments, interim, transcript, problem, start, stop }
}
