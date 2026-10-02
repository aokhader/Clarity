import { ArrowRight, Briefcase, FolderOpen, Gavel, LayoutGrid, ShieldAlert, type LucideIcon } from 'lucide-react'
import { Link } from 'react-router'

import { UserSwitcher } from '@/components/firm/UserSwitcher'
import { MATTER_VIEWS, type MatterViewId } from '@/lib/matterViews'
import { cn } from '@/lib/utils'

const VIEW_ICONS: Record<MatterViewId, LucideIcon> = {
  overview: LayoutGrid,
  attorney: Briefcase,
  provider: ShieldAlert,
  documents: FolderOpen,
}

/** The dark rail beside the firm view: product name, the four views, and the stub user. */
export function FirmSidebar({ view }: { view: MatterViewId }) {
  return (
    <aside className="sticky top-0 flex h-screen flex-col bg-slate-900 text-white">
      <div className="flex items-center gap-3 border-b border-slate-800 px-6 pt-6 pb-6">
        <span className="flex size-10 items-center justify-center rounded-lg bg-primary">
          <Gavel aria-hidden className="size-5" />
        </span>
        <div>
          <p className="text-lg leading-tight font-bold tracking-tight">Clarity</p>
          <p className="text-[10px] font-semibold tracking-[0.12em] text-slate-400">CASE BRIEF</p>
        </div>
      </div>
      <nav aria-label="Views" className="flex flex-col gap-2 px-4 py-6">
        {MATTER_VIEWS.map(({ id, label }) => {
          const active = id === view
          const Icon = VIEW_ICONS[id]
          return (
            <Link
              key={id}
              to={{ search: id === 'overview' ? '' : `?view=${id}` }}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'flex items-center gap-3 rounded-lg px-4 py-3 text-[15px] font-medium transition-colors',
                active
                  ? 'bg-primary text-white shadow-lg shadow-blue-600/35'
                  : 'text-slate-200 hover:bg-slate-800 hover:text-white',
              )}
            >
              <Icon aria-hidden className={cn('size-[1.15rem]', active ? 'text-white' : 'text-slate-400')} />
              <span className="flex-1">{label}</span>
              {active && <ArrowRight aria-hidden className="size-4" />}
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
