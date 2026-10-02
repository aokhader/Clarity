import { ScrollText } from 'lucide-react'

import { ApiError } from '@/api/client'
import { useMatterBrief } from '@/api/matters'
import { BriefSentence } from '@/components/firm/BriefSentence'
import { LoadError } from '@/components/shared/LoadError'
import { Panel } from '@/components/shared/Panel'
import { Skeleton } from '@/components/ui/skeleton'

/** The story of the case in sentences, each ending in the sources that support it. */
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

  const { headline, sentences, open_questions: openQuestions } = brief.data
  return (
    <Panel title="Brief" icon={<ScrollText />}>
      <p className="font-serif text-2xl leading-snug font-semibold">{headline}</p>
      {sentences.length > 0 ? (
        <p className="mt-3 font-serif text-brief">
          {sentences.map((sentence) => (
            <BriefSentence key={sentence.text} sentence={sentence} />
          ))}
        </p>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">
          The brief's sentences cite facts that cannot be shown, so they are hidden.
        </p>
      )}
      {openQuestions.length > 0 && (
        <div className="mt-4 border-t pt-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Not answered by the file
          </h3>
          <ul className="mt-1.5 list-disc space-y-0.5 pl-5 text-sm">
            {openQuestions.map((question) => (
              <li key={question}>{question}</li>
            ))}
          </ul>
        </div>
      )}
    </Panel>
  )
}
