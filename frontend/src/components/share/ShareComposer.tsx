import { Dialog } from 'radix-ui'

import type { ProviderOut } from '@/api/types'
import { ShareComposerForm } from '@/components/share/ShareComposerForm'

type ShareComposerProps = {
  matterId: number
  userId: number
  /** The provider being shared with; null when the composer is closed. */
  provider: ProviderOut | null
  onClose: () => void
}

/** A full-height dialog. Keyed by provider, so each opening starts from the default settings. */
export function ShareComposer({ matterId, userId, provider, onClose }: ShareComposerProps) {
  return (
    <Dialog.Root open={provider !== null} onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-foreground/20" />
        <Dialog.Content className="fixed inset-4 flex flex-col overflow-hidden rounded-lg border bg-card focus:outline-none">
          {provider && (
            <ShareComposerForm key={provider.contact_id} matterId={matterId} userId={userId} provider={provider} />
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
