import { X } from 'lucide-react'
import { Dialog } from 'radix-ui'
import { useMemo, useState } from 'react'

import { useCreateShare, useDraftPreview } from '@/api/shares'
import type { ProviderOut, ShareCreate, ShareOut, ShareSettings } from '@/api/types'
import { CopyLinkButton } from '@/components/share/CopyLinkButton'
import { ProviderView } from '@/components/share/ProviderView'
import { ProviderViewSkeleton } from '@/components/share/ProviderViewSkeleton'
import { SettingToggles } from '@/components/share/SettingToggles'
import { ShareItemsList } from '@/components/share/ShareItemsList'
import { DEFAULT_SHARE_SETTINGS } from '@/components/share/shareSettings'
import { LoadError } from '@/components/shared/LoadError'
import { Button } from '@/components/ui/button'
import { useDebouncedValue } from '@/lib/useDebouncedValue'
import { useSourceDrawer } from '@/lib/useSourceDrawer'

const NOTE_DEBOUNCE_MS = 400
// null leaves the expiry to the firm's configured default.
const EXPIRY_OPTIONS: { label: string; days: number | null }[] = [
  { label: 'Firm default', days: null },
  { label: '7 days', days: 7 },
  { label: '90 days', days: 90 },
]

type ShareComposerFormProps = {
  matterId: number
  userId: number
  provider: ProviderOut
}

/** Left: what to release. Right: the provider page exactly as the server would build it. */
export function ShareComposerForm({ matterId, userId, provider }: ShareComposerFormProps) {
  const [settings, setSettings] = useState<ShareSettings>(DEFAULT_SHARE_SETTINGS)
  const [hidden, setHidden] = useState<number[]>([])
  const [note, setNote] = useState('')
  const [expiryDays, setExpiryDays] = useState<number | null>(null)
  const [created, setCreated] = useState<ShareOut | null>(null)
  const settledNote = useDebouncedValue(note, NOTE_DEBOUNCE_MS)

  const draft = useMemo<ShareCreate>(
    () => ({
      provider_contact_id: provider.contact_id,
      settings,
      hidden_fact_ids: hidden,
      note: settledNote.trim() || null,
      expires_in_days: expiryDays,
    }),
    [provider.contact_id, settings, hidden, settledNote, expiryDays],
  )
  const preview = useDraftPreview(matterId, draft)
  const create = useCreateShare(matterId)
  const drawer = useSourceDrawer()

  function toggleHidden(factId: number, hide: boolean) {
    setHidden((current) => (hide ? [...current, factId] : current.filter((id) => id !== factId)))
  }

  function createLink() {
    const body = { ...draft, note: note.trim() || null }
    create.mutate({ userId, body }, { onSuccess: setCreated })
  }

  return (
    <>
      <header className="flex items-start justify-between gap-4 border-b px-6 py-4">
        <div>
          <Dialog.Title className="text-lg font-semibold">Share case status with {provider.name}</Dialog.Title>
          <Dialog.Description className="text-sm text-muted-foreground">
            The provider sees exactly the preview on the right, through a private link.
          </Dialog.Description>
        </div>
        <Dialog.Close asChild>
          <Button variant="ghost" size="icon-sm" aria-label="Close">
            <X />
          </Button>
        </Dialog.Close>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[26rem_minmax(0,1fr)]">
        <fieldset disabled={created !== null} className="min-h-0 space-y-6 overflow-y-auto border-r p-6">
          <SettingToggles
            settings={settings}
            onChange={(setting, on) => setSettings((current) => ({ ...current, [setting]: on }))}
          />
          <p className="rounded-md bg-muted px-3 py-2 text-xs">
            Never shared under any setting: case value, strategy, negotiations, and internal notes.
          </p>
          {preview.data && <ShareItemsList items={preview.data.items} onToggle={toggleHidden} />}
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Note to the provider
            </span>
            <textarea
              value={note}
              onChange={(event) => setNote(event.target.value)}
              rows={3}
              className="mt-2 w-full rounded-md border bg-card px-3 py-2 text-sm"
              placeholder="Optional"
            />
          </label>
          <fieldset>
            <legend className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Link expires after
            </legend>
            <div className="mt-2 flex gap-4 text-sm">
              {EXPIRY_OPTIONS.map((option) => (
                <label key={option.label} className="flex cursor-pointer items-center gap-2">
                  <input
                    type="radio"
                    name="expiry"
                    className="accent-primary"
                    checked={expiryDays === option.days}
                    onChange={() => setExpiryDays(option.days)}
                  />
                  {option.label}
                </label>
              ))}
            </div>
          </fieldset>
        </fieldset>

        <div className="min-h-0 overflow-y-auto bg-background p-8">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Preview: what {provider.name} sees
          </p>
          <div className="mx-auto max-w-2xl rounded-lg border bg-card p-8">
            {preview.isPending ? (
              <ProviderViewSkeleton />
            ) : preview.isError ? (
              <LoadError what="the preview" error={preview.error} onRetry={() => void preview.refetch()} />
            ) : (
              <ProviderView payload={preview.data.payload} onOpenSource={(item) => drawer.open(item.fact_id)} />
            )}
          </div>
        </div>
      </div>

      <footer className="flex items-center justify-end gap-3 border-t px-6 py-3">
        {create.isError && (
          <p role="alert" className="mr-auto text-sm text-danger">
            Could not create the link. {create.error.message}
          </p>
        )}
        {created ? (
          <>
            <code className="mr-auto truncate text-xs text-muted-foreground">{created.url}</code>
            <CopyLinkButton url={created.url} />
            <Dialog.Close asChild>
              <Button size="sm">Done</Button>
            </Dialog.Close>
          </>
        ) : (
          <Button size="sm" onClick={createLink} disabled={create.isPending}>
            {create.isPending ? 'Creating…' : 'Create link'}
          </Button>
        )}
      </footer>
    </>
  )
}
