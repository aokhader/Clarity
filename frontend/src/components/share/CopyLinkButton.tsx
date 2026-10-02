import { Check, Link } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'

const CONFIRM_MS = 2000

export function CopyLinkButton({ url, label = 'Copy link' }: { url: string; label?: string }) {
  const [copied, setCopied] = useState(false)
  useEffect(() => {
    if (!copied) return
    const timer = setTimeout(() => setCopied(false), CONFIRM_MS)
    return () => clearTimeout(timer)
  }, [copied])

  async function copy() {
    await navigator.clipboard.writeText(url)
    setCopied(true)
  }

  return (
    <Button variant="outline" size="sm" onClick={() => void copy()} aria-live="polite">
      {copied ? <Check aria-hidden className="text-success" /> : <Link aria-hidden />}
      {copied ? 'Copied' : label}
    </Button>
  )
}
