import { Phone } from 'lucide-react'

import { CopyLinkButton } from '@/components/share/CopyLinkButton'
import { Button } from '@/components/ui/button'
import { telHref } from '@/lib/phone'

/**
 * The hand-off: a `tel:` link that opens this computer's phone app or a paired phone.
 * Clarity never learns whether the call connected. The number is always shown with a
 * Copy button, and gets no link when its shape could not be dialled safely.
 */
export function DialLink({ phone }: { phone: string }) {
  const href = telHref(phone)
  return (
    <div className="flex flex-wrap items-center gap-3">
      {href ? (
        <Button asChild size="sm">
          <a href={href}>
            <Phone aria-hidden />
            Dial {phone}
          </a>
        </Button>
      ) : (
        <span className="text-sm">
          <span className="font-medium tabular-nums">{phone}</span>
          <span className="ml-2 text-muted-foreground">cannot be dialled from here; copy it into your phone.</span>
        </span>
      )}
      <CopyLinkButton url={phone} label="Copy number" />
    </div>
  )
}
