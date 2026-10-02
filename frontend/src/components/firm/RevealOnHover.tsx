import type { ReactNode } from 'react'

/**
 * Keeps source chips out of the way until the reader points at, or tabs into, the fact
 * they belong to (the nearest `group/src` ancestor). The chips stay in the layout and in
 * the tab order, so every fact on screen is still one click from its source.
 */
export function RevealOnHover({ children }: { children: ReactNode }) {
  return (
    <span className="opacity-0 transition-opacity group-focus-within/src:opacity-100 group-hover/src:opacity-100">
      {children}
    </span>
  )
}
