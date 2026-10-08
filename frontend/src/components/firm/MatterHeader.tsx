import type { MatterHeaderOut } from '@/api/types'
import { ClientAvatar } from '@/components/firm/ClientAvatar'
import { StagePill } from '@/components/firm/StagePill'

/** The client card that opens the overview: photo or initials, name, stage, and matter. */
export function MatterHeader({ header }: { header: MatterHeaderOut }) {
  const name = header.client?.name ?? header.description ?? `Matter ${header.matter_id}`
  const subtitle = [header.description, header.display_number].filter(Boolean).join(' · ')
  return (
    <section
      aria-label="Client"
      className="flex items-center gap-6 rounded-xl border bg-card p-6"
    >
      <ClientAvatar name={name} avatarUrl={header.client?.avatar_url ?? null} />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="font-serif text-3xl font-semibold">{name}</h2>
          <StagePill stage={header.stage} />
        </div>
        {subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}
      </div>
    </section>
  )
}
