import { keepPreviousData, skipToken, useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'

import { apiGet, apiPost } from './client'
import type { ChatAskIn, ChatBudgetOut, ChatThreadOut, ChatThreadSummaryOut, ChatTurnOut, FactOut } from './types'
import { useDebouncedValue } from '@/lib/useDebouncedValue'

/** How often a thread is checked while an answer is being written on the server. */
const ANSWER_POLL_MS = 1_500
/** Search waits for typing to pause this long, so each keystroke is not a request. */
const SEARCH_DEBOUNCE_MS = 150
/** The server refuses a shorter query (docs/chat-contract.md). */
export const SEARCH_MIN_CHARS = 2
const SEARCH_LIMIT = 12

const chatKey = (matterId: number) => ['matters', matterId, 'chat'] as const
const threadKey = (matterId: number, threadId: number | null) => [...chatKey(matterId), 'thread', threadId] as const
const threadsKey = (matterId: number) => [...chatKey(matterId), 'threads'] as const
const budgetKey = (matterId: number) => [...chatKey(matterId), 'budget'] as const

/** The matter's threads that are not archived, newest first. */
export function useChatThreads(matterId: number) {
  return useQuery({
    queryKey: threadsKey(matterId),
    queryFn: () => apiGet<ChatThreadSummaryOut[]>(`/matters/${matterId}/chat/threads`),
  })
}

/** One thread with its turns, polled while any answer is still being written. */
export function useChatThread(matterId: number, threadId: number | null) {
  return useQuery({
    queryKey: threadKey(matterId, threadId),
    queryFn:
      threadId === null ? skipToken : () => apiGet<ChatThreadOut>(`/matters/${matterId}/chat/threads/${threadId}`),
    refetchInterval: (query) =>
      query.state.data?.turns.some((turn) => turn.status === 'running') ? ANSWER_POLL_MS : false,
  })
}

/** Today's chat spend on the matter against its daily cap, and whether chat is configured. */
export function useChatBudget(matterId: number) {
  return useQuery({
    queryKey: budgetKey(matterId),
    queryFn: () => apiGet<ChatBudgetOut>(`/matters/${matterId}/chat/budget`),
  })
}

/**
 * Put a turn the server just returned into its thread's cache, so it shows at once,
 * then fetch the thread so the server's own copy replaces it. A new thread is seeded
 * with the question as its title until then.
 */
async function storeTurn(queryClient: QueryClient, matterId: number, turn: ChatTurnOut) {
  queryClient.setQueryData<ChatThreadOut>(threadKey(matterId, turn.thread_id), (thread) =>
    thread
      ? { ...thread, turns: [...thread.turns.filter((t) => t.turn_id !== turn.turn_id), turn] }
      : { thread_id: turn.thread_id, title: turn.question, created_at: turn.asked_at, updated_at: turn.asked_at, turns: [turn] },
  )
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: threadKey(matterId, turn.thread_id) }),
    queryClient.invalidateQueries({ queryKey: threadsKey(matterId) }),
    queryClient.invalidateQueries({ queryKey: budgetKey(matterId) }),
  ])
}

/**
 * Ask a question, with the items pointed at as ids. The server starts the answer in the
 * background and returns the running turn (or no_model); the thread is then polled.
 * A spent daily budget comes back as a 429.
 */
export function useAsk(matterId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationKey: [...chatKey(matterId), 'ask'],
    mutationFn: ({ userId, body }: { userId: number; body: ChatAskIn }) =>
      apiPost<ChatTurnOut>(`/matters/${matterId}/chat/ask`, { userId }, body),
    onSuccess: (turn) => storeTurn(queryClient, matterId, turn),
    // A refusal may be the daily cap: the budget shows why, wherever Ask is offered.
    onError: () => queryClient.invalidateQueries({ queryKey: budgetKey(matterId) }),
  })
}

/** Ask again for a turn that failed or found no model configured. */
export function useRetryTurn(matterId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, turnId }: { userId: number; turnId: number }) =>
      apiPost<ChatTurnOut>(`/matters/${matterId}/chat/turns/${turnId}/retry`, { userId }),
    onSuccess: (turn) => storeTurn(queryClient, matterId, turn),
    onError: () => queryClient.invalidateQueries({ queryKey: budgetKey(matterId) }),
  })
}

/** Take a thread off the list; it stays in the database. */
export function useArchiveThread(matterId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, threadId }: { userId: number; threadId: number }) =>
      apiPost<null>(`/matters/${matterId}/chat/threads/${threadId}/archive`, { userId }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: threadsKey(matterId) }),
  })
}

/**
 * Records matching what is typed, at word starts, ranked by the server, with no model
 * call. It waits for typing to pause, starts at two characters, and keeps the last hits
 * on screen while the next ones load.
 */
export function useAskSearch(matterId: number, q: string) {
  const settled = useDebouncedValue(q.trim(), SEARCH_DEBOUNCE_MS)
  const enabled = settled.length >= SEARCH_MIN_CHARS
  return useQuery({
    queryKey: [...chatKey(matterId), 'search', settled],
    queryFn: enabled
      ? () =>
          apiGet<FactOut[]>(
            `/matters/${matterId}/search?${new URLSearchParams({ q: settled, limit: String(SEARCH_LIMIT) })}`,
          )
      : skipToken,
    placeholderData: keepPreviousData,
  })
}
