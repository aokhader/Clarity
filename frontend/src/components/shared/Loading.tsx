import type { ReactNode } from 'react'

type LoadingProps = {
  /** What is loading, read out by screen readers: "Loading the brief". */
  label: string
  className?: string
  /** The skeletons drawn in its place. */
  children: ReactNode
}

/** A loading placeholder that says so: skeletons for the eye, a status for screen readers. */
export function Loading({ label, className, children }: LoadingProps) {
  return (
    <div role="status" className={className}>
      <span className="sr-only">{label}</span>
      {children}
    </div>
  )
}
