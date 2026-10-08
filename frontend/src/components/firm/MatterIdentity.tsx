import { ChevronRight } from 'lucide-react'
import { Fragment, useEffect, useId, type ReactNode } from 'react'
import { Link } from 'react-router'

import type { MatterHeaderOut } from '@/api/types'
import { ClientAvatar } from '@/components/firm/ClientAvatar'
import { StageTrack } from '@/components/firm/StageTrack'
import { SourceChip } from '@/components/shared/SourceChip'
import { formatDate, formatElapsed } from '@/lib/format'

const CRUMB_LINK = 'text-primary underline-offset-4 hover:underline'

type MatterIdentityProps = {
  header: MatterHeaderOut
  /** The view on screen, the breadcrumb's last item and the start of the tab's title. */
  viewLabel: string
}

/**
 * Who and what the matter is, at the top of every view: the breadcrumb, the client's
 * photo and name (the page's one h1), one case line, and the stage. Nothing is shown
 * without a source, so there is no responsible attorney and no practice area.
 */
export function MatterIdentity({ header, viewLabel }: MatterIdentityProps) {
  const incidentId = useId()
  const clientName = header.client?.name ?? null
  const name = clientName ?? header.description ?? `Matter ${header.matter_id}`

  useEffect(() => {
    document.title = `${viewLabel} – ${name} – Clarity`
  }, [viewLabel, name])

  const { incident } = header
  const caseLine: ReactNode[] = []
  // When the description stands in for the name, the case line does not repeat it.
  if (header.description && clientName !== null) caseLine.push(header.description)
  if (header.display_number) caseLine.push(`Matter ${header.display_number}`)
  if (incident) {
    caseLine.push(
      <span className="inline-flex flex-wrap items-center gap-1.5">
        <span id={incidentId} className="tabular-nums">
          Incident {formatDate(incident.on)}, {formatElapsed(incident.on)} ago
        </span>
        <SourceChip fact={incident.fact} describedBy={incidentId} />
      </span>,
    )
  }

  return (
    <header className="flex flex-col gap-4">
      <nav aria-label="Breadcrumb">
        <ol className="flex flex-wrap items-center gap-1.5 text-sm text-muted-foreground">
          <li>
            <Link to="/" className={CRUMB_LINK}>
              Cases
            </Link>
          </li>
          <li className="flex items-center gap-1.5">
            <ChevronRight aria-hidden className="size-3.5" />
            <Link to={{ search: '' }} className={CRUMB_LINK}>
              {name}
            </Link>
          </li>
          <li className="flex items-center gap-1.5">
            <ChevronRight aria-hidden className="size-3.5" />
            <span aria-current="page" className="text-foreground">
              {viewLabel}
            </span>
          </li>
        </ol>
      </nav>
      <div className="flex items-center gap-4">
        <ClientAvatar name={name} avatarUrl={header.client?.avatar_url ?? null} />
        <div className="flex min-w-0 flex-col gap-1">
          <h1 className="font-serif text-3xl leading-tight font-semibold text-pretty">{name}</h1>
          {caseLine.length > 0 && (
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground">
              {caseLine.map((part, index) => (
                <Fragment key={index}>
                  {index > 0 && <span aria-hidden>·</span>}
                  {part}
                </Fragment>
              ))}
            </p>
          )}
        </div>
      </div>
      <StageTrack stage={header.stage} />
    </header>
  )
}
