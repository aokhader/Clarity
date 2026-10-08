import { Check } from 'lucide-react'

import type { CaseStage, StageOut } from '@/api/types'
import { RevealOnHover } from '@/components/firm/RevealOnHover'
import { Panel } from '@/components/shared/Panel'
import { SourceChipList } from '@/components/shared/SourceChipList'
import { cn } from '@/lib/utils'

const STEPS = ['Intake', 'Treatment', 'Demand', 'Negotiation', 'Litigation'] as const

/** Where each stage sits on the five-step road; settled and closed matters are past the end. */
const STEP_OF_STAGE: Record<CaseStage, number> = {
  intake: 1,
  treating: 2,
  treatment_complete: 2,
  demand: 3,
  negotiation: 4,
  litigation: 5,
  settled: 6,
  closed: 6,
}

/** The case's progress from intake to litigation, from the stage fact. */
export function RoadmapCard({ stage }: { stage: StageOut }) {
  const current = stage.stage === null ? null : STEP_OF_STAGE[stage.stage]
  // The bar runs to the middle of the current step's column.
  const fill = current === null ? 0 : Math.min(100, (current - 1) * 20 + 10)
  return (
    <Panel
      title="Roadmap"
      actions={
        <span className="group/src flex items-center gap-2 text-sm text-muted-foreground">
          {stage.inferred && <span className="text-warning">Stage inferred</span>}
          <RevealOnHover>
            <SourceChipList facts={stage.facts} max={2} />
          </RevealOnHover>
        </span>
      }
    >
      {current === null ? (
        <p className="text-sm text-muted-foreground">Stage not found in file.</p>
      ) : (
        <div className="relative pt-2 pb-2">
          <div className="absolute inset-x-0 top-5 h-[3px] rounded-full bg-slate-100" />
          <div className="absolute top-5 left-0 h-[3px] rounded-full bg-blue-500" style={{ width: `${fill}%` }} />
          <ol className="relative grid grid-cols-5">
            {STEPS.map((label, index) => {
              const step = index + 1
              const done = step < current
              const isCurrent = step === current
              return (
                <li key={label} className="flex flex-col items-center gap-3" aria-current={isCurrent ? 'step' : undefined}>
                  <span
                    className={cn(
                      'flex items-center justify-center rounded-full text-xs font-bold',
                      done && 'size-[26px] border-3 border-blue-100 bg-primary text-white',
                      isCurrent && '-mt-0.5 size-[30px] border-3 border-blue-200 bg-card text-primary ring-3 ring-blue-50',
                      !done && !isCurrent && 'size-[26px] border-3 border-card bg-slate-100 text-slate-400',
                    )}
                  >
                    {done ? <Check aria-hidden className="size-3.5" strokeWidth={3} /> : step}
                  </span>
                  <span
                    className={cn(
                      'text-[15px] font-medium',
                      isCurrent ? 'text-primary' : done ? 'text-slate-800' : 'text-slate-400',
                    )}
                  >
                    {label}
                  </span>
                </li>
              )
            })}
          </ol>
        </div>
      )}
    </Panel>
  )
}
