import { X } from 'lucide-react'
import { Dialog } from 'radix-ui'

import { useSharePreview } from '@/api/shares'
import { providerUpdateText } from '@/components/share/providerUpdateText'
import { UpdateDraftEditor } from '@/components/share/UpdateDraftEditor'
import { LoadError } from '@/components/shared/LoadError'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

type SendUpdateFormProps = {
  shareId: number
  url: string
  providerName: string
}

/** The update's first draft comes from the share's preview: the payload the link serves. */
export function SendUpdateForm({ shareId, url, providerName }: SendUpdateFormProps) {
  const preview = useSharePreview(shareId, true)
  return (
    <>
      <header className="flex items-start justify-between gap-4 border-b px-6 py-4">
        <div>
          <Dialog.Title className="text-lg font-semibold">Send an update to {providerName}</Dialog.Title>
          <Dialog.Description className="text-sm text-muted-foreground">
            Edit the message. Every amount and date is checked against the file as you write. Clarity sends nothing
            itself: the message opens in your own email or messaging app.
          </Dialog.Description>
        </div>
        <Dialog.Close asChild>
          <Button variant="ghost" size="icon-sm" aria-label="Close">
            <X />
          </Button>
        </Dialog.Close>
      </header>
      {preview.isPending && (
        <div className="space-y-3 p-6" aria-label="Preparing the update">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-80 w-full" />
        </div>
      )}
      {preview.isError && (
        <div className="p-6">
          <LoadError what="the update" error={preview.error} onRetry={() => void preview.refetch()} />
        </div>
      )}
      {preview.isSuccess && (
        <UpdateDraftEditor shareId={shareId} message={providerUpdateText(preview.data.payload, url)} />
      )}
    </>
  )
}
