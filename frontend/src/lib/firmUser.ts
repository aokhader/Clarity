import { useSyncExternalStore } from 'react'

// The stub firm user picked in the header switcher. Kept in this viewer's browser as a
// convenience; there is no real login, and the API trusts the X-User-Id header.
const STORAGE_KEY = 'clarity.firmUserId'
const listeners = new Set<() => void>()

function readStored(): number | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw !== null && /^\d+$/.test(raw) ? Number(raw) : null
  } catch {
    return null
  }
}

let selectedId = readStored()

export function selectFirmUser(id: number): void {
  selectedId = id
  try {
    localStorage.setItem(STORAGE_KEY, String(id))
  } catch {
    // Storage can be blocked; the choice then lasts until the tab closes.
  }
  for (const listener of listeners) listener()
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useSelectedFirmUserId(): number | null {
  return useSyncExternalStore(subscribe, () => selectedId)
}
