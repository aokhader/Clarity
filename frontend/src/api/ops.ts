import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { ApiError, apiGet, apiPost } from './client'
import type { CostOut, DigestStartIn, HealthOut, RunStatusOut } from './types'

/** How often a running sync or digest is checked for completion. */
const POLL_MS = 2_000

export function useHealth() {
  return useQuery({
    queryKey: ['ops', 'health'],
    queryFn: () => apiGet<HealthOut>('/ops/health'),
  })
}

export function useDigestCost(matterId: number) {
  return useQuery({
    queryKey: ['ops', 'cost', matterId],
    queryFn: () => apiGet<CostOut>(`/ops/cost?matter_id=${matterId}`),
  })
}

export type Job = 'sync' | 'digest'

/**
 * A job's state on the server, including a failure before its run began (no Clio token,
 * no matching matter), which leaves no run row to report it.
 */
export function useJobStatus(job: Job) {
  return useQuery({
    queryKey: ['ops', job, 'status'],
    queryFn: () => apiGet<RunStatusOut>(`/ops/${job}/status`),
  })
}

/** Start a background job, or join the one already running (409), and wait for it to end. */
async function runJob(job: Job, body?: DigestStartIn): Promise<RunStatusOut> {
  try {
    await apiPost<RunStatusOut>(`/ops/${job}`, {}, body)
  } catch (error) {
    if (!(error instanceof ApiError && error.status === 409)) throw error
  }
  for (;;) {
    await new Promise((resolve) => setTimeout(resolve, POLL_MS))
    const status = await apiGet<RunStatusOut>(`/ops/${job}/status`)
    if (!status.running) {
      if (status.start_failure) throw new Error(`The ${job} could not start: ${status.start_failure.error}`)
      if (status.last_run?.error) throw new Error(`The ${job} failed: ${status.last_run.error}`)
      return status
    }
  }
}

export type ResyncPhase = 'idle' | 'syncing' | 'digesting'

/**
 * Pull the matter from Clio again, then digest what changed. Both run on the server in
 * the background; this only starts them and waits. Every cached view refreshes after.
 */
export function useResync() {
  const queryClient = useQueryClient()
  const [phase, setPhase] = useState<ResyncPhase>('idle')
  const mutation = useMutation({
    mutationFn: async () => {
      setPhase('syncing')
      await runJob('sync')
      setPhase('digesting')
      await runJob('digest')
    },
    onSettled: async () => {
      setPhase('idle')
      await queryClient.invalidateQueries()
    },
  })
  return { ...mutation, phase }
}

/**
 * Digest again, asking the model anew for the calls that failed before instead of answering
 * them from the cached failure (D29), as `cli digest --retry-failed` does. It makes model
 * calls, which cost money, so the footer offers it only when some calls failed.
 */
export function useRetryFailedCalls() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => runJob('digest', { retry_failed: true }),
    onSettled: () => queryClient.invalidateQueries(),
  })
}
