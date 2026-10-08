import { useId } from 'react'

/** What the brief found the file does not answer. Neutral, not amber: a gap is not a status (docs/ui.md). */
export function OpenQuestions({ questions }: { questions: string[] }) {
  const headingId = useId()
  if (questions.length === 0) return null
  return (
    <section aria-labelledby={headingId} className="mt-5 border-t pt-4">
      <h3 id={headingId} className="text-xs font-semibold tracking-[0.08em] text-muted-foreground uppercase">
        Not answered by the file
      </h3>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-[15px]">
        {questions.map((question) => (
          <li key={question}>{question}</li>
        ))}
      </ul>
    </section>
  )
}
