import { ApiError } from '@/api/client'
import { useMatterBrief } from '@/api/matters'
import { BriefSentence } from '@/components/firm/BriefSentence'
import { LoadError } from '@/components/shared/LoadError'
import { Panel } from '@/components/shared/Panel'
import { Skeleton } from '@/components/ui/skeleton'

/**
 * The story of the case: a headline, then sentences that each end in the sources they
 * rest on, then what the file does not answer. The server drops any sentence that cites
 * a fact that cannot be shown, and checks every amount and date against today's file.
 */
export function Brief({ matterId }: { matterId: number }) {
  const brief = useMatterBrief(matterId)

  if (brief.isPending) {
    return (
      <Panel title="Brief">
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
      <Panel title="Brief">
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

  const { headline, headline_facts: headlineFacts, headline_mentions: headlineMentions, sentences } = brief.data
  const openQuestions = brief.data.open_questions
  return (
    <Panel title="Brief">
      <p className="text-xl leading-snug font-bold text-pretty">
        <BriefSentence text={headline} facts={headlineFacts} mentions={headlineMentions} />
      </p>
      {sentences.length > 0 ? (
        <p className="mt-3 font-serif text-brief text-pretty">
          {sentences.map((sentence, index) => (
            <BriefSentence key={index} text={sentence.text} facts={sentence.facts} mentions={sentence.mentions} />
          ))}
        </p>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">
          None of the brief's sentences can be shown with a source, so they are hidden.
        </p>
      )}
      {openQuestions.length > 0 && (
        // Neutral, not amber: a gap in the file is not a status (docs/ui.md).
        <div className="mt-5 border-t pt-4">
          <h3 className="text-xs font-semibold tracking-[0.08em] text-muted-foreground uppercase">
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
