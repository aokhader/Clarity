/**
 * A `tel:` link for a North American number, in the global form RFC 3966 asks for:
 * `tel:+1` and ten digits. Any other shape gets no link, since a misread digit would ring
 * a stranger; the number is still shown with a Copy button.
 */
export function telHref(phone: string): string | null {
  const digits = phone.replace(/\D/g, '')
  if (digits.length === 10) return `tel:+1${digits}`
  if (digits.length === 11 && digits.startsWith('1')) return `tel:+${digits}`
  return null
}
