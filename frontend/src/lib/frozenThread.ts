import { createContext, useContext } from 'react'

/** The closed thread a chip is drawn in. */
export type FrozenThread = { threadId: number }

/**
 * Set around a closed thread's turns (D54). A closed thread is the firm's record of what
 * was cited, so its chips open the sources frozen when it closed, not today's file, where
 * a re-read may have replaced the fact. Null everywhere else.
 */
export const FrozenThreadContext = createContext<FrozenThread | null>(null)

/** The closed thread around this component, or null outside one. */
export function useFrozenThread(): FrozenThread | null {
  return useContext(FrozenThreadContext)
}
