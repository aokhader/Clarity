import { useMatterBrief } from '@/api/matters'
import { BriefSentence } from '@/components/firm/BriefSentence'
import { MarginCited } from '@/components/firm/MarginCited'
import { OpenQuestions } from '@/components/firm/OpenQuestions'
import { Loading } from '@/components/shared/Loading'
import { Section } from '@/components/shared/Section'
import { Skeleton } from '@/components/ui/skeleton'

/**
 * The brief's sentences, one row each with its chips in the margin, then what the file
 * does not answer. The server drops any sentence citing a fact that cannot be shown and
 * checks every amount and date against today's file.
 */
export function WhereItStands({ matterId }: { matterId: number }) {
  const brief = useMatterBrief(matterId)
  // The bottom line says when there is no brief or it failed, with the retry; this section stays out of the way.
  if (brief.isError) return null
  return (
    <Section title="Where it stands">
      {brief.isPending ? (
        <Loading label="Loading the brief" className="space-y-3">
          <Skeleton className="h-6" />
          <Skeleton className="h-6" />
          <Skeleton className="h-6 w-2/3" />
        </Loading>
      ) : (
        <>
          {brief.data.sentences.length > 0 ? (
            <ul className="@container">
              {brief.data.sentences.map((sentence, index) => (
                <MarginCited key={index} facts={sentence.facts} className="text-base leading-relaxed text-pretty">
                  <BriefSentence text={sentence.text} mentions={sentence.mentions} cited={sentence.facts.length > 0} />
                </MarginCited>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">
              None of the brief&apos;s sentences can be shown with a source, so they are hidden.
            </p>
          )}
          <OpenQuestions questions={brief.data.open_questions} />
        </>
      )}
    </Section>
  )
}
