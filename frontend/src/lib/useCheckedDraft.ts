import { useDraftCheck, type CheckedDraft, type DraftTarget } from '@/api/shares'
import { useDebouncedValue } from '@/lib/useDebouncedValue'

/** How long typing must pause before the draft is checked. */
const CHECK_DEBOUNCE_MS = 500

export type DraftCheckState = {
  /** The latest check, possibly of slightly older text while the next one runs. */
  checked: CheckedDraft | null
  /** The check ran on exactly the text in the editor, so its offsets apply to it. */
  current: boolean
  checking: boolean
  error: Error | null
  retry: () => void
  /**
   * Why the text may not leave Clarity yet, or null when it may: it must be checked as it
   * stands, and no sentence may be locked by "Don't send".
   */
  blocked: string | null
}

/** The server's check of the editor's text, run once typing pauses. */
export function useCheckedDraft(target: DraftTarget, text: string): DraftCheckState {
  const settled = useDebouncedValue(text, CHECK_DEBOUNCE_MS)
  const query = useDraftCheck(target, settled)
  const empty = text.trim() === ''
  // An emptied editor has nothing to check, so the last check is not shown for it.
  const checked = empty ? null : (query.data ?? null)
  const current = checked !== null && checked.text === text
  const error = !empty && query.isError ? query.error : null
  let blocked: string | null = null
  if (empty) blocked = 'There is nothing to send.'
  else if (error) blocked = 'It could not be checked. Retry the check.'
  else if (!current) blocked = 'Wait for the check to finish.'
  else if (checked.check.verdict === 'do_not_send') blocked = "Remove the sentences marked Don't send."
  return {
    checked,
    current,
    checking: !empty && error === null && (!current || query.isFetching),
    error,
    retry: () => void query.refetch(),
    blocked,
  }
}
