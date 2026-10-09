import { Check } from 'lucide-react'
import { useId } from 'react'

import type { StageOut } from '@/api/types'
import { SourceChipList } from '@/components/shared/SourceChipList'
import { STAGE_LABELS, STAGE_STEPS, STEP_OF_STAGE } from '@/lib/labels'
import { cn } from '@/lib/utils'

/**
 * A step before the current one is an earlier stage, not a completed one: a case in
 * litigation can still be treating (D40). Only a settled or closed case completes them.
 */
type StepState = 'completed' | 'earlier stage' | 'current' | 'not started'

const MARK_STYLES: Record<StepState, string> = {
  completed: 'bg-foreground text-background',
  'earlier stage': 'bg-foreground text-background',
  current: 'border-2 border-foreground bg-card text-foreground',
  // The input token keeps a step not yet reached at 3:1 against the page.
  'not started': 'border-2 border-input bg-card text-muted-foreground',
}

const LABEL_STYLES: Record<StepState, string> = {
  completed: 'text-foreground',
  'earlier stage': 'text-foreground',
  current: 'font-semibold text-foreground',
  'not started': 'text-muted-foreground',
}

/**
 * The case's stage on the five-step track, shown once on every view. Which step is
 * current is said in text as well as marked, and the stage fact is cited. Earlier steps
 * are filled but carry no check mark. A settled or closed matter completes the track and
 * is named by its own label, never "Step 6 of 5".
 */
export function StageTrack({ stage }: { stage: StageOut }) {
  const summaryId = useId()
  if (stage.stage === null) return <p className="text-sm text-muted-foreground">Stage not found in file</p>

  const position = STEP_OF_STAGE[stage.stage]
  const label = STAGE_LABELS[stage.stage]
  const summary = position === 'past_end' ? label : `Step ${position} of ${STAGE_STEPS.length}: ${label}`
  const stateOf = (step: number): StepState => {
    if (position === 'past_end') return 'completed'
    if (step < position) return 'earlier stage'
    return step === position ? 'current' : 'not started'
  }

  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
      <ol aria-label="Case progress" className="flex flex-wrap items-center gap-y-2">
        {STAGE_STEPS.map((step, index) => {
          const state = stateOf(index + 1)
          return (
            <li key={step} aria-current={state === 'current' ? 'step' : undefined} className="flex items-center">
              {index > 0 && (
                <span
                  aria-hidden
                  className={cn('mx-2 h-0.5 w-5 rounded-full', state === 'not started' ? 'bg-input' : 'bg-foreground')}
                />
              )}
              <span
                aria-hidden
                className={cn(
                  'flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold',
                  MARK_STYLES[state],
                )}
              >
                {state === 'completed' ? <Check className="size-3.5" strokeWidth={3} /> : index + 1}
              </span>
              <span className={cn('ml-2 text-sm', LABEL_STYLES[state])}>
                {STAGE_LABELS[step]}
                <span className="sr-only">, {state}</span>
              </span>
            </li>
          )
        })}
      </ol>
      <p className="flex flex-wrap items-center gap-2 text-sm">
        <span id={summaryId} className="font-medium" title={stage.label ? `Recorded as "${stage.label}"` : undefined}>
          {summary}
        </span>
        {stage.inferred && (
          <span className="rounded-sm border border-dashed border-warning px-1.5 text-xs font-medium text-warning">
            inferred
          </span>
        )}
        <SourceChipList facts={stage.facts} max={2} describedBy={summaryId} />
      </p>
    </div>
  )
}
