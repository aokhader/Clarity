import { useAsk, useChatBudget, useChatThread } from '@/api/chat'
import { useFirmUser } from '@/api/users'
import { useAskContext } from '@/lib/askState'
import { BUDGET_SPENT, askErrorText, budgetSpent, isBudgetRefusal } from '@/lib/chatErrors'

type SubmitOptions = {
  /** Open the side panel on the thread once the question is accepted. */
  openPanel: boolean
}

/**
 * Send the question being written, with the items pointed at as ids, to the panel's
 * thread (a follow-up) or a new one. Both the Ask bar and the composers use it, so they
 * refuse for the same reasons: no question, the day's budget spent, an answer still
 * being written on the thread, or no firm user yet.
 */
export function useAskQuestion(matterId: number) {
  const ask = useAskContext()
  const user = useFirmUser()
  const mutation = useAsk(matterId)
  const budget = useChatBudget(matterId)
  const thread = useChatThread(matterId, ask.threadId)

  const answering = thread.data?.turns.some((turn) => turn.status === 'running') ?? false
  const spent = budgetSpent(budget.data) || isBudgetRefusal(mutation.error)
  /** Why Ask is off, when it is; null when a question can be sent. */
  const blocked = spent
    ? BUDGET_SPENT
    : answering
      ? 'The answer is still being written. Wait for it, or start a new question.'
      : user === null
        ? 'Loading the firm user.'
        : null

  const submit = (question: string, { openPanel }: SubmitOptions) => {
    const text = question.trim()
    if (text === '' || blocked !== null || user === null || mutation.isPending) return
    mutation.mutate(
      { userId: user.id, body: { question: text, items: ask.items.map((item) => item.ref), thread_id: ask.threadId } },
      {
        onSuccess: (turn) => {
          ask.setThreadId(turn.thread_id)
          ask.clear()
          if (openPanel) ask.openPanel()
          ask.announce('Question sent. The answer appears once the file has been read.')
        },
      },
    )
  }

  return {
    submit,
    pending: mutation.isPending,
    blocked,
    /** The last refusal, in words; the budget refusal is already said by `blocked`. */
    error: mutation.error && !isBudgetRefusal(mutation.error) ? askErrorText(mutation.error) : null,
    budget: budget.data,
    following: ask.threadId !== null,
  }
}
