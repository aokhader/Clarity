import { Briefcase, FolderOpen, Gavel, LayoutGrid, Menu, Phone, ShieldAlert, X, type LucideIcon } from 'lucide-react'
import { useId, useState } from 'react'
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

/**
 * The light rail beside the firm view: product name, the views, and the stub user. Below
 * the lg breakpoint it is a top bar whose menu button discloses the same views, so the
 * page reflows to 320px (WCAG 1.4.10).
 */
export function FirmSidebar({ view }: { view: MatterViewId }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuId = useId()
  return (
    <aside
      aria-label="Clarity"
      className="border-b bg-card lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col lg:overflow-y-auto lg:border-r lg:border-b-0"
    >
      <div className="flex items-center gap-2 px-3 py-2.5 sm:gap-3 sm:px-4 lg:border-b lg:px-5 lg:py-5">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-md border border-foreground text-foreground">
          <Gavel aria-hidden className="size-[1.1rem]" />
        </span>
        <div className="min-w-0">
          <p className="text-lg leading-tight font-semibold tracking-tight">Clarity</p>
          {/* Sentence case in the source, capitals by style: screen readers spell out literal capitals.
              Left out of the narrowest top bar, so the menu button fits at 320px. */}
          <p className="hidden text-[11px] font-medium tracking-[0.12em] text-muted-foreground uppercase sm:block">
            Case brief
          </p>
        </div>
        <button
          type="button"
          aria-expanded={menuOpen}
          aria-controls={menuId}
          onClick={() => setMenuOpen((open) => !open)}
          className="ml-auto flex shrink-0 items-center gap-1.5 rounded-md border border-input px-2.5 py-1.5 text-sm font-medium lg:hidden"
        >
          {menuOpen ? <X aria-hidden className="size-4" /> : <Menu aria-hidden className="size-4" />}
          Menu
        </button>
      </div>
      <div id={menuId} className={cn('flex-col border-t lg:flex lg:flex-1 lg:border-t-0', menuOpen ? 'flex' : 'hidden')}>
        <nav aria-label="Views" className="flex flex-col gap-0.5 py-4">
          {MATTER_VIEWS.map(({ id, label }) => {
            const active = id === view
            const Icon = VIEW_ICONS[id]
            return (
              <Link
                key={id}
                to={{ search: id === 'overview' ? '' : `?view=${id}` }}
                aria-current={active ? 'page' : undefined}
                onClick={() => setMenuOpen(false)}
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
        <div className="lg:mt-auto">
          <UserSwitcher />
        </div>
      </div>
    </aside>
  )
}
