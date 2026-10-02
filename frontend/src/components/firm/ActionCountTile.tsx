import type { LucideIcon } from 'lucide-react'

import { cn } from '@/lib/utils'

export type CountTone = 'danger' | 'info' | 'warning' | 'neutral'

const TONES: Record<CountTone, string> = {
  danger: 'border-red-100 bg-red-50 text-red-700',
  info: 'border-blue-100 bg-blue-50 text-blue-700',
  warning: 'border-orange-100 bg-orange-50 text-orange-700',
  neutral: 'border-slate-200 bg-slate-50 text-slate-700',
}

type ActionCountTileProps = {
  Icon: LucideIcon
  value: string
  label: string
  tone: CountTone
}

/** One count above the action table. */
export function ActionCountTile({ Icon, value, label, tone }: ActionCountTileProps) {
  return (
    <div className={cn('flex flex-col items-center gap-1 rounded-xl border px-3 py-4', TONES[tone])}>
      <Icon aria-hidden className="mb-0.5 size-[1.05rem]" />
      <span className="text-3xl leading-tight font-extrabold tabular-nums">{value}</span>
      <span className="text-xs font-medium tracking-[0.08em] uppercase">{label}</span>
    </div>
  )
}
