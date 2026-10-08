import type { LucideIcon } from 'lucide-react'

import { cn } from '@/lib/utils'

/** Red for what is overdue; every other count is neutral. */
export type CountTone = 'danger' | 'neutral'

const TONES: Record<CountTone, string> = {
  danger: 'bg-danger-soft text-danger',
  neutral: 'bg-muted text-foreground',
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
    <div className={cn('flex flex-col items-center gap-1 rounded-lg px-3 py-4', TONES[tone])}>
      <Icon aria-hidden className="mb-0.5 size-[1.05rem]" />
      <span className="text-3xl leading-tight font-semibold tabular-nums">{value}</span>
      <span className="text-xs font-medium tracking-[0.08em] uppercase">{label}</span>
    </div>
  )
}
