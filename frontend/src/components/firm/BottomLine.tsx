import { ApiError } from '@/api/client'
import { useMatterBrief } from '@/api/matters'
import { BriefSentence } from '@/components/firm/BriefSentence'
import { MarginCited } from '@/components/firm/MarginCited'
import { LoadError } from '@/components/shared/LoadError'
import { Loading } from '@/components/shared/Loading'
import { Section } from '@/components/shared/Section'
import { Skeleton } from '@/components/ui/skeleton'

/**
 * The brief's headline, the case in one sentence, citing the facts it rests on (D14).
 * It also says when there is no brief yet or it failed to load, for the brief's other
 * sections as well (WhereItStands).
 */
export function BottomLine({ matterId }: { matterId: number }) {
  const brief = useMatterBrief(matterId)
  return (
    <Section title="The bottom line">
      {brief.isPending && (
        <Loading label="Loading the brief" className="space-y-2">
          <Skeleton className="h-8 w-4/5" />
          <Skeleton className="h-8 w-3/5" />
        </Loading>
      )}
      {brief.isError &&
        (brief.error instanceof ApiError && brief.error.status === 404 ? (
          <p className="text-sm text-muted-foreground">No brief yet. The digest writes it once the facts are scored.</p>
        ) : (
          <LoadError what="the brief" error={brief.error} onRetry={() => void brief.refetch()} />
        ))}
      {brief.isSuccess && (
        <div className="@container">
          <MarginCited as="div" facts={brief.data.headline_facts} className="font-serif text-headline text-pretty">
            <BriefSentence
              text={brief.data.headline}
              mentions={brief.data.headline_mentions}
              cited={brief.data.headline_facts.length > 0}
            />
          </MarginCited>
        </div>
      )}
    </Section>
  )
}
