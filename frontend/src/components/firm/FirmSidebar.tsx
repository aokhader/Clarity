import { CalendarDays, DollarSign, FolderOpen, Gavel, ListOrdered, ScrollText, Stethoscope } from 'lucide-react'
import { Link } from 'react-router'

import { cn } from '@/lib/utils'

/** In-page sections the sidebar jumps to; the ids are set in `MatterPage`. */
const SECTIONS = [
  { href: '#figures', label: 'Financial overview', Icon: DollarSign },
  { href: '#brief', label: 'Brief', Icon: ScrollText },
  { href: '#feed', label: 'What matters', Icon: ListOrdered },
  { href: '#actions', label: 'Action board', Icon: CalendarDays },
  { href: '#providers', label: 'Providers', Icon: Stethoscope },
] as const

const LINK = 'flex items-center gap-3 rounded-lg px-4 py-2.5 text-[15px] font-medium text-slate-200 transition-colors hover:bg-slate-800 hover:text-white'

/** The dark rail beside the firm view: product name, the overview's sections, and the documents page. */
export function FirmSidebar({ showDocuments }: { showDocuments: boolean }) {
  return (
    <aside className="sticky top-0 flex h-screen flex-col bg-slate-900 text-white">
      <div className="flex items-center gap-3 border-b border-slate-800 px-6 pt-6 pb-6">
        <span className="flex size-10 items-center justify-center rounded-lg bg-primary">
          <Gavel aria-hidden className="size-5" />
        </span>
        <div>
          <p className="text-lg font-bold leading-tight tracking-tight">Clarity</p>
          <p className="text-[10px] font-semibold tracking-[0.12em] text-slate-400">CASE BRIEF</p>
        </div>
      </div>
      <nav aria-label="Sections" className="flex flex-col gap-1 px-4 py-6">
        {SECTIONS.map(({ href, label, Icon }) => (
          <Link key={href} to={{ search: '', hash: href }} className={LINK}>
            <Icon aria-hidden className="size-[1.15rem] text-slate-400" />
            {label}
          </Link>
        ))}
        <Link
          to={{ search: '?view=documents' }}
          aria-current={showDocuments ? 'page' : undefined}
          className={cn(LINK, 'mt-2', showDocuments && 'bg-primary text-white hover:bg-primary')}
        >
          <FolderOpen aria-hidden className={cn('size-[1.15rem]', showDocuments ? 'text-white' : 'text-slate-400')} />
          Documents
        </Link>
      </nav>
    </aside>
  )
}
