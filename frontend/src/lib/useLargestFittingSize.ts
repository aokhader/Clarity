import { useLayoutEffect, useRef, useState } from 'react'

/**
 * The largest of `sizes` (text-size classes, largest first) at which the element's content
 * is no wider than the element, so a figure steps down a size instead of being cut off.
 * Measured before paint, again when `content` changes, and whenever the element's width does.
 * Pass `sizes` as a constant, since a new array each render would measure each render.
 */
export function useLargestFittingSize<E extends HTMLElement>(sizes: readonly [string, ...string[]], content: string) {
  const ref = useRef<E>(null)
  const [size, setSize] = useState<string>(sizes[0])

  useLayoutEffect(() => {
    const element = ref.current
    if (element === null) return
    const smallest = sizes[sizes.length - 1] ?? sizes[0]
    const fit = () => {
      // Try each size on the element itself, so measuring takes no extra renders. The
      // class left on it is the one React renders next, so the two stay in step.
      element.classList.remove(...sizes)
      const fitting =
        sizes.find((candidate) => {
          element.classList.add(candidate)
          const fits = element.scrollWidth <= element.clientWidth
          element.classList.remove(candidate)
          return fits
        }) ?? smallest
      element.classList.add(fitting)
      setSize(fitting)
    }
    fit()
    let width = element.clientWidth
    const observer = new ResizeObserver(() => {
      // Only the width decides what fits; the height follows the size chosen.
      if (element.clientWidth === width) return
      width = element.clientWidth
      fit()
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [sizes, content])

  return { ref, size }
}
