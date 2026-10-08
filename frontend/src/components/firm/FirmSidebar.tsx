import { Briefcase, FolderOpen, Gavel, LayoutGrid, Phone, ShieldAlert, type LucideIcon } from 'lucide-react'
import { Link } from 'react-router'

import { UserSwitcher } from '@/components/firm/UserSwitcher'
import { MATTER_VIEWS, type MatterViewId } from '@/lib/matterViews'
import { cn } from '@/lib/utils'

const VIEW_ICONS: Record<MatterViewId, LucideIcon> = {
  overview: LayoutGrid,
  attorney: Briefcase,
  provider: ShieldAlert,
  documents: FolderOpen,
  calls: Phone,
}

/** The light rail beside the firm view: product name, the views, and the stub user. */
export function FirmSidebar({ view }: { view: MatterViewId }) {
  return (
    <aside aria-label="Clarity" className="sticky top-0 flex h-screen flex-col overflow-y-auto border-r bg-card">
      <div className="flex items-center gap-3 border-b px-5 py-5">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-md border border-foreground text-foreground">
          <Gavel aria-hidden className="size-[1.1rem]" />
        </span>
        <div>
          <p className="text-lg leading-tight font-semibold tracking-tight">Clarity</p>
          {/* Sentence case in the source, capitals by style: screen readers spell out literal capitals. */}
          <p className="text-[11px] font-medium tracking-[0.12em] text-muted-foreground uppercase">Case brief</p>
        </div>
      </div>
      <nav aria-label="Views" className="flex flex-col gap-0.5 py-4">
        {MATTER_VIEWS.map(({ id, label }) => {
          const active = id === view
          const Icon = VIEW_ICONS[id]
          return (
            <Link
              key={id}
              to={{ search: id === 'overview' ? '' : `?view=${id}` }}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'flex items-center gap-3 border-l-3 py-2.5 pr-5 pl-4 text-[15px] transition-colors focus-visible:-outline-offset-2',
                active
                  ? 'border-primary bg-muted font-medium text-foreground'
                  : 'border-transparent text-muted-foreground hover:bg-muted hover:text-foreground',
              )}
            >
              <Icon aria-hidden className={cn('size-[1.1rem]', active ? 'text-foreground' : 'text-muted-foreground')} />
              {label}
            </Link>
          )
        })}
      </nav>
      <div className="mt-auto">
        <UserSwitcher />
      </div>
    </aside>
  )
}
