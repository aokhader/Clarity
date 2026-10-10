import { X } from 'lucide-react'
import { Dialog } from 'radix-ui'
import { useId, useState } from 'react'

import { Button } from '@/components/ui/button'
import { CONSENT_TEXT } from '@/lib/callConsent'

type ConsentDialogProps = {
  /** Who is on the other end, as the list names them. */
  name: string
  onAgreed: () => void
  onDeclined: () => void
  /** Back out without asking: nothing is recorded and the call panel is unchanged. */
  onClose: () => void
}

/**
 * Consent before anything is transcribed. The attorney reads the wording to everyone on
 * the call and confirms they all agreed; that exact wording is stored with the call.
 * Mounted only while asking, so every ask starts unconfirmed.
 */
export function ConsentDialog({ name, onAgreed, onDeclined, onClose }: ConsentDialogProps) {
  const [confirmed, setConfirmed] = useState(false)
  const checkboxId = useId()
  return (
    <Dialog.Root open onOpenChange={(next) => !next && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-foreground/20" />
        <Dialog.Content className="fixed top-1/2 left-1/2 w-[min(40rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 space-y-4 rounded-lg border bg-card p-6 focus:outline-none">
          <div className="flex items-start justify-between gap-4">
            <Dialog.Title className="text-lg font-semibold">Ask before transcribing</Dialog.Title>
            <Dialog.Close asChild>
              <Button variant="ghost" size="icon-sm" aria-label="Cancel: close without asking">
                <X />
              </Button>
            </Dialog.Close>
          </div>
          <Dialog.Description className="text-sm text-muted-foreground">
            California requires every party to a confidential call to agree before it is recorded, and Clarity treats
            transcription as recording. Read this to everyone on the call with {name}:
          </Dialog.Description>
          <blockquote className="border-l-2 border-muted-foreground bg-muted px-4 py-3 font-serif text-base leading-relaxed">
            {CONSENT_TEXT}
          </blockquote>
          <label htmlFor={checkboxId} className="flex items-start gap-2 text-sm">
            <input
              id={checkboxId}
              type="checkbox"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
              className="mt-0.5 accent-primary"
            />
            Everyone on the call heard this and agreed to transcription.
          </label>
          <p className="text-xs text-muted-foreground">
            The wording above is stored with the call as the consent given. This is a design rule, not legal advice.
          </p>
          <div className="flex justify-end gap-3">
            {/* Apart from the two answers, so backing out is never mistaken for one. */}
            <Dialog.Close asChild>
              <Button variant="ghost" size="sm" className="mr-auto">
                Cancel
              </Button>
            </Dialog.Close>
            <Button variant="outline" size="sm" onClick={onDeclined}>
              Declined, call without transcription
            </Button>
            <Button size="sm" disabled={!confirmed} onClick={onAgreed}>
              Agreed, start transcribing
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
