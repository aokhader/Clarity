import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiGet, apiPost, apiPut } from './client'
import type { CallDetailOut, CallNumberIn, CallOut, CallStartIn, CallTargetOut, CallTranscriptIn } from './types'

/** How often a call's notes are checked while the server writes them. */
const NOTES_POLL_MS = 2_000

/** Who to call next: open items waiting on someone, with each contact's number. */
export function useCallTargets(matterId: number) {
  return useQuery({
    queryKey: ['matters', matterId, 'calls', 'next'],
    queryFn: () => apiGet<CallTargetOut[]>(`/matters/${matterId}/calls/next`),
  })
}

/** The matter's calls, newest first. */
export function useMatterCalls(matterId: number) {
  return useQuery({
    queryKey: ['matters', matterId, 'calls'],
    queryFn: () => apiGet<CallOut[]>(`/matters/${matterId}/calls`),
  })
}

/** Store a typed name and number in Clarity, never in Clio (D15). */
export function useAddCallNumber(matterId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: CallNumberIn) => apiPost<CallTargetOut>(`/matters/${matterId}/call-numbers`, {}, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['matters', matterId, 'calls', 'next'] }),
  })
}

/** Open a call on the server. It refuses without consent, and stores the wording shown. */
export function useStartCall(matterId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, body }: { userId: number; body: CallStartIn }) =>
      apiPost<CallOut>(`/matters/${matterId}/calls`, { userId }, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['matters', matterId, 'calls'], exact: true }),
  })
}

/** Save the whole transcript so far; the last save after the call is marked final. */
export function saveTranscript(callId: number, body: CallTranscriptIn): Promise<CallOut> {
  return apiPut<CallOut>(`/calls/${callId}/transcript`, {}, body)
}

/** End the call. The server starts writing its notes in the background. */
export function useEndCall(matterId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ callId, transcript }: { callId: number; transcript: string }) => {
      await saveTranscript(callId, { text: transcript, final: true })
      return apiPost<CallOut>(`/calls/${callId}/end`)
    },
    onSuccess: (call) =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: ['calls', call.call_id] }),
        queryClient.invalidateQueries({ queryKey: ['matters', matterId, 'calls'] }),
      ]),
  })
}

/** A call with its transcript and notes, polled while the notes are being written. */
export function useCallDetail(callId: number | null) {
  return useQuery({
    queryKey: ['calls', callId],
    queryFn: () => apiGet<CallDetailOut>(`/calls/${callId}`),
    enabled: callId !== null,
    refetchInterval: (query) => {
      const call = query.state.data?.call
      // An ended call's notes may not have started yet; keep checking until they settle.
      const writing = call?.notes_status === 'running' || (call?.notes_status === 'not_started' && call.ended_at !== null)
      return writing ? NOTES_POLL_MS : false
    },
  })
}
