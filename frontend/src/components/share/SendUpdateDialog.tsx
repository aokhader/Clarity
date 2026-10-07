import { Send } from 'lucide-react'
import { Dialog } from 'radix-ui'

import { SendUpdateForm } from '@/components/share/SendUpdateForm'
import { Button } from '@/components/ui/button'

type SendUpdateDialogProps = {
  shareId: number
  /** The provider's live link, quoted at the end of the message. */
  url: string
  providerName: string
}

/**
 * Drafts a status update for a provider, to send from the firm's own mail or messaging
 * app. Each opening starts from a fresh draft of what the link shows. Clarity sends nothing.
 */
export function SendUpdateDialog({ shareId, url, providerName }: SendUpdateDialogProps) {
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <Button variant="outline" size="sm">
          <Send aria-hidden />
          Send update
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-foreground/20" />
        <Dialog.Content className="fixed inset-4 mx-auto flex max-w-6xl flex-col overflow-hidden rounded-lg border bg-card focus:outline-none">
          <SendUpdateForm shareId={shareId} url={url} providerName={providerName} />
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
