import { Check, ChevronDown, Copy, Mail, MessageSquare, Send } from 'lucide-react'
import { useEffect, useId, useState } from 'react'

import { useSharePreview } from '@/api/shares'
import { providerUpdateText } from '@/components/share/providerUpdateText'
import { Button } from '@/components/ui/button'

const CONFIRM_MS = 2000

type SendUpdateMenuProps = {
  shareId: number
  /** The provider's live link, quoted at the end of the message. */
  url: string
}

/**
 * Drafts a status update for a provider in the firm's own mail or messaging app, or
 * copies it. The text comes from the share's preview, the same payload the link serves,
 * so it says nothing the link would not. Clarity sends nothing itself.
 */
export function SendUpdateMenu({ shareId, url }: SendUpdateMenuProps) {
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const preview = useSharePreview(shareId, open)
  const menuId = useId()

  useEffect(() => {
    if (!copied) return
    const timer = setTimeout(() => setCopied(false), CONFIRM_MS)
    return () => clearTimeout(timer)
  }, [copied])

  const message = preview.isSuccess ? providerUpdateText(preview.data.payload, url) : null

  async function copy(text: string) {
    await navigator.clipboard.writeText(text)
    setCopied(true)
  }

  return (
    <div className="flex flex-col items-end gap-1.5">
      <Button
        variant="outline"
        size="sm"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((value) => !value)}
      >
        <Send aria-hidden />
        Send update
        <ChevronDown aria-hidden className={open ? 'rotate-180' : undefined} />
      </Button>
      {open && (
        <div id={menuId} className="flex flex-col items-end gap-1">
          {preview.isError && (
            <p role="alert" className="text-xs text-danger">
              Could not prepare the update. {preview.error.message}
            </p>
          )}
          {preview.isPending && <p className="text-xs text-muted-foreground">Preparing the update…</p>}
          {message && (
            <>
              <Button asChild variant="ghost" size="xs">
                <a
                  href={`mailto:?subject=${encodeURIComponent(message.subject)}&body=${encodeURIComponent(message.body)}`}
                >
                  <Mail aria-hidden />
                  Email
                </a>
              </Button>
              <Button asChild variant="ghost" size="xs">
                <a href={`sms:?&body=${encodeURIComponent(message.short)}`}>
                  <MessageSquare aria-hidden />
                  Text message
                </a>
              </Button>
              <Button variant="ghost" size="xs" onClick={() => void copy(message.body)} aria-live="polite">
                {copied ? <Check aria-hidden className="text-success" /> : <Copy aria-hidden />}
                {copied ? 'Copied' : 'Copy text'}
              </Button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
