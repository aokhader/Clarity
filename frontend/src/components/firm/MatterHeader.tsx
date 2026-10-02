import type { MatterHeaderOut } from '@/api/types'
import { ClientAvatar } from '@/components/firm/ClientAvatar'
import { StagePill } from '@/components/firm/StagePill'
import { UserSwitcher } from '@/components/firm/UserSwitcher'
import { SourceChip } from '@/components/shared/SourceChip'
import { STALE_CONTACT_DAYS } from '@/lib/facts'
import { daysFromToday, formatDate, formatDaysAgo, formatElapsed } from '@/lib/format'
import { cn } from '@/lib/utils'

export function MatterHeader({ header }: { header: MatterHeaderOut }) {
  const { client, incident, last_client_contact: contact } = header
  const name = client?.name ?? header.description ?? `Matter ${header.matter_id}`
  const subtitle = [header.description, header.display_number].filter(Boolean).join(' · ')
  const staleContact = contact !== null && -daysFromToday(contact.on) > STALE_CONTACT_DAYS

  return (
    <header className="flex items-start justify-between gap-6 pb-5">
      <div className="flex items-start gap-4">
        <ClientAvatar name={name} avatarUrl={client?.avatar_url ?? null} />
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{name}</h1>
          {subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}
          <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm">
            <div className="flex items-center gap-1.5">
              <dt className="text-muted-foreground">Incident</dt>
              <dd className="flex items-center gap-1.5 tabular-nums">
                {incident ? (
                  <>
                    {formatDate(incident.on)}
                    <span className="text-muted-foreground">({formatElapsed(incident.on)} ago)</span>
                    <SourceChip fact={incident.fact} />
                  </>
                ) : (
                  <span className="text-muted-foreground">Not found in file</span>
                )}
              </dd>
            </div>
            <div className="flex items-center gap-1.5">
              <dt className="text-muted-foreground">Last client contact</dt>
              <dd className={cn('flex items-center gap-1.5', staleContact && 'font-medium text-warning')}>
                {contact ? (
                  <>
                    {formatDaysAgo(contact.on)}
                    <SourceChip fact={contact.fact} />
                  </>
                ) : (
                  <span className="text-muted-foreground">None found in file</span>
                )}
              </dd>
            </div>
          </dl>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <StagePill stage={header.stage} />
        <UserSwitcher />
      </div>
    </header>
  )
}
