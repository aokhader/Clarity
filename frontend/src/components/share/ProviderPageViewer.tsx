import { X } from 'lucide-react'
import { Dialog } from 'radix-ui'
import { useState } from 'react'

import { useProviderSource } from '@/api/provider'
import type { ProviderItemOut } from '@/api/types'
import { LoadError } from '@/components/shared/LoadError'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

type ProviderPageViewerProps = {
  token: string
  /** The bill or record whose cited page is open; null when closed. */
  item: ProviderItemOut | null
  onClose: () => void
}

/** The one document page a provider's own bill or record cites, with the quoted line above it. */
export function ProviderPageViewer({ token, item, onClose }: ProviderPageViewerProps) {
  const source = useProviderSource(token, item?.fact_id ?? null)
  const page = source.data?.page ?? null
  const [unloadedUrl, setUnloadedUrl] = useState<string | null>(null)
  return (
    <Dialog.Root open={item !== null} onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-foreground/20" />
        <Dialog.Content className="fixed inset-y-0 right-0 flex w-full max-w-2xl flex-col border-l bg-card focus:outline-none">
          <header className="flex items-start justify-between gap-4 border-b px-5 py-3">
            <div className="min-w-0">
              <Dialog.Title className="font-medium">{item?.label}</Dialog.Title>
              <Dialog.Description className="text-xs text-muted-foreground">
                {page ? `Page ${page.page_no} of the document on file` : 'The page this item comes from'}
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <Button variant="ghost" size="icon-sm" aria-label="Close">
                <X />
              </Button>
            </Dialog.Close>
          </header>
          <div className="flex-1 space-y-4 overflow-y-auto p-5">
            {source.isPending && <Skeleton className="h-[36rem] w-full" />}
            {source.isError && (
              <LoadError what="this page" error={source.error} onRetry={() => void source.refetch()} />
            )}
            {source.data?.quote && (
              <blockquote className="rounded-md border-l-2 border-foreground/40 bg-muted px-3 py-2 font-serif text-sm">
                {source.data.quote}
              </blockquote>
            )}
            {source.data &&
              (page && unloadedUrl !== page.image_url ? (
                <img
                  key={page.image_url}
                  src={page.image_url}
                  alt={`Page ${page.page_no} of the document`}
                  onError={() => setUnloadedUrl(page.image_url)}
                  className="w-full rounded-md border"
                />
              ) : (
                <p className="text-sm text-muted-foreground">The page image is not available.</p>
              ))}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
