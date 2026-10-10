import type { AskItemRef } from '@/api/types'
import { encodeAskTarget } from '@/lib/askItems'
import { useAskPicking } from '@/lib/askState'
import type { StarterKind } from '@/lib/askStarters'

/** What marks an element as something to point at and ask about. */
export type AskTargetProps = {
  'data-ask-item'?: string
  tabIndex?: number
  'aria-describedby'?: string
}

/**
 * For a list whose rows are drawn in a loop, where a hook cannot be called per row: a
 * function giving each row's target props (see useAskTarget).
 */
export function useAskTargetProps(): (ref: AskItemRef | null, starter: StarterKind) => AskTargetProps {
  const picking = useAskPicking()
  return (ref, starter) => {
    if (picking === null || ref === null) return {}
    const props: AskTargetProps = { 'data-ask-item': encodeAskTarget(ref, starter) }
    if (picking.picking) {
      // In pick mode a target can be reached with Tab and chosen with Enter (WCAG 2.5.7).
      props.tabIndex = 0
      props['aria-describedby'] = picking.hintId
    }
    return props
  }
}

/**
 * Props to spread on a row, tile or step, so the Ask handle can be dropped on it or it
 * can be picked (D49). It is a hook, not a wrapper, so a table row stays a `<tr>`.
 * Outside AskProvider (the provider page), or with no ref, it gives nothing, and the
 * element is no target.
 */
export function useAskTarget(ref: AskItemRef | null, starter: StarterKind): AskTargetProps {
  return useAskTargetProps()(ref, starter)
}
