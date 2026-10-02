import { CircleHelp, ScrollText } from 'lucide-react'

import { ApiError } from '@/api/client'
import { useMatterBrief } from '@/api/matters'
import { LoadError } from '@/components/shared/LoadError'
import { Panel } from '@/components/shared/Panel'
import { Skeleton } from '@/components/ui/skeleton'

/** The brief's headline and what the file does not answer; the sentence body is not shown. */
export function Brief({ matterId }: { matterId: number }) {
  const brief = useMatterBrief(matterId)

  if (brief.isPending) {
    return (
      <Panel title="Brief" icon={<ScrollText />}>
        <div className="space-y-3" aria-label="Loading the brief">
          <Skeleton className="h-8 w-4/5" />
          <Skeleton className="h-5" />
          <Skeleton className="h-5" />
          <Skeleton className="h-5 w-2/3" />
        </div>
      </Panel>
    )
  }

  if (brief.isError) {
    return (
      <Panel title="Brief" icon={<ScrollText />}>
        {brief.error instanceof ApiError && brief.error.status === 404 ? (
          <p className="text-sm text-muted-foreground">
            No brief yet. The digest writes it once the facts are scored.
          </p>
        ) : (
          <LoadError what="the brief" error={brief.error} onRetry={() => void brief.refetch()} />
        )}
      </Panel>
    )
  }

  const { headline, open_questions: openQuestions } = brief.data
  return (
    <Panel title="Brief" icon={<ScrollText />}>
      <p className="text-xl leading-snug font-bold text-pretty">{headline}</p>
      {openQuestions.length > 0 && (
        <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-4">
          <h3 className="flex items-center gap-2 text-xs font-semibold tracking-[0.08em] text-amber-700 uppercase">
            <CircleHelp aria-hidden className="size-4" />
            Not answered by the file
          </h3>
          <ul className="mt-2.5 list-disc space-y-1 pl-5 text-[15px]">
            {openQuestions.map((question) => (
              <li key={question}>{question}</li>
            ))}
          </ul>
        </div>
      )}
    </Panel>
  )
}
