import { Check, Copy, Mail, MessageSquare } from 'lucide-react'
import { useEffect, useState } from 'react'

import { DraftCheckView } from '@/components/share/DraftCheckView'
import type { ProviderUpdateMessage } from '@/components/share/providerUpdateText'
import { Button } from '@/components/ui/button'
import { useCheckedDraft } from '@/lib/useCheckedDraft'
import { cn } from '@/lib/utils'

const CONFIRM_MS = 2000

type Format = 'email' | 'text'
const FORMATS: { id: Format; label: string }[] = [
  { id: 'email', label: 'Email' },
  { id: 'text', label: 'Text message' },
]

type UpdateDraftEditorProps = {
  shareId: number
  /** The generated first drafts: the full update for email, a short one for a text. */
  message: ProviderUpdateMessage
}

/**
 * The update as an editable draft on the left and the server's check of it on the right.
 * It can leave Clarity only once checked as written, and never with a sentence marked
 * "Don't send".
 */
export function UpdateDraftEditor({ shareId, message }: UpdateDraftEditorProps) {
  const [format, setFormat] = useState<Format>('email')
  const [drafts, setDrafts] = useState<Record<Format, string>>({ email: message.body, text: message.short })
  const [copied, setCopied] = useState(false)
  const draft = drafts[format]
  const check = useCheckedDraft({ shareId }, draft)

  useEffect(() => {
    if (!copied) return
    const timer = setTimeout(() => setCopied(false), CONFIRM_MS)
    return () => clearTimeout(timer)
  }, [copied])

  const setDraft = (text: string) => setDrafts((current) => ({ ...current, [format]: text }))
  const href =
    format === 'email'
      ? `mailto:?subject=${encodeURIComponent(message.subject)}&body=${encodeURIComponent(draft)}`
      : `sms:?&body=${encodeURIComponent(draft)}`
  const OpenIcon = format === 'email' ? Mail : MessageSquare
  const openLabel = format === 'email' ? 'Open in email' : 'Open in messages'

  async function copy() {
    await navigator.clipboard.writeText(draft)
    setCopied(true)
  }

  return (
    <>
      <div className="grid min-h-0 flex-1 grid-cols-2">
        <div className="flex min-h-0 flex-col gap-3 border-r p-6">
          <div role="group" aria-label="Message format" className="flex gap-2">
            {FORMATS.map((option) => (
              <button
                key={option.id}
                type="button"
                aria-pressed={format === option.id}
                onClick={() => setFormat(option.id)}
                className={cn(
                  'rounded-md border px-3 py-1 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-ring',
                  format === option.id ? 'border-primary bg-primary text-primary-foreground' : 'hover:bg-muted',
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
          <label className="flex min-h-0 flex-1 flex-col gap-1.5">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Message</span>
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              className="min-h-0 flex-1 resize-none rounded-md border bg-card px-3 py-2 text-sm leading-6"
            />
          </label>
        </div>
        <section aria-label="Checked against the file" className="min-h-0 overflow-y-auto bg-background p-6">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Checked against the file
          </h3>
          <DraftCheckView state={check} onChange={setDraft} alwaysShowText />
        </section>
      </div>
      <footer className="flex items-center justify-end gap-3 border-t px-6 py-3">
        {check.blocked && <p className="mr-auto text-sm text-muted-foreground">{check.blocked}</p>}
        {check.blocked ? (
          <Button size="sm" disabled>
            <OpenIcon aria-hidden />
            {openLabel}
          </Button>
        ) : (
          <Button asChild size="sm">
            <a href={href}>
              <OpenIcon aria-hidden />
              {openLabel}
            </a>
          </Button>
        )}
        <Button
          variant="outline"
          size="sm"
          disabled={check.blocked !== null}
          onClick={() => void copy()}
          aria-live="polite"
        >
          {copied ? <Check aria-hidden className="text-success" /> : <Copy aria-hidden />}
          {copied ? 'Copied' : 'Copy text'}
        </Button>
      </footer>
    </>
  )
}
