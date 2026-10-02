function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * Locate a quote in a text, ignoring differences in whitespace and case, the same
 * leniency the pipeline's quote check allows. Returns [start, end) or null.
 */
export function findQuote(text: string, quote: string): [number, number] | null {
  const words = quote.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return null
  const match = new RegExp(words.map(escapeRegExp).join('\\s+'), 'i').exec(text)
  return match ? [match.index, match.index + match[0].length] : null
}

/**
 * Notes can be stored as rich text. Show their text content, never their markup:
 * DOMParser builds an inert document, so nothing in it runs.
 */
export function plainText(text: string): string {
  if (!/<\/?[a-z][^>]*>/i.test(text)) return text
  const withBreaks = text.replace(/<br\s*\/?>/gi, '\n').replace(/<\/(p|div|li)>/gi, '\n')
  return new DOMParser().parseFromString(withBreaks, 'text/html').body.textContent ?? ''
}
