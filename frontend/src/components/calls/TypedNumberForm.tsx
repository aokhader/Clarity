import { useState, type FormEvent } from 'react'

import { useAddCallNumber } from '@/api/calls'
import { ApiError } from '@/api/client'
import type { CallTargetOut } from '@/api/types'
import { Panel } from '@/components/shared/Panel'
import { Button } from '@/components/ui/button'
import { telHref } from '@/lib/phone'

type TypedNumberFormProps = {
  matterId: number
  /** Opens the call with the new number; null while another call is on. */
  onAdded: ((target: CallTargetOut) => void) | null
}

/**
 * A number the file does not have, typed by the attorney (D15). It is stored only in
 * Clarity, labelled as typed, and never written to Clio.
 */
export function TypedNumberForm({ matterId, onAdded }: TypedNumberFormProps) {
  const add = useAddCallNumber(matterId)
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const complete = name.trim() !== '' && phone.trim() !== ''
  const undiallable = phone.trim() !== '' && telHref(phone) === null

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!complete) return
    add.mutate(
      { name: name.trim(), phone: phone.trim() },
      {
        onSuccess: (target) => {
          setName('')
          setPhone('')
          onAdded?.(target)
        },
      },
    )
  }

  return (
    <Panel title="Call a number not in Clio">
      <form onSubmit={submit} className="space-y-3">
        <p className="text-sm text-muted-foreground">
          Stored only in Clarity and never written to Clio. Use it for someone the file has no number for.
        </p>
        <label className="block text-sm">
          <span className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">Name</span>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            autoComplete="off"
            className="mt-1 w-full rounded-md border bg-card px-3 py-1.5"
          />
        </label>
        <label className="block text-sm">
          <span className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">Phone number</span>
          <input
            type="tel"
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            autoComplete="off"
            className="mt-1 w-full rounded-md border bg-card px-3 py-1.5 tabular-nums"
          />
        </label>
        {undiallable && (
          <p className="text-xs text-muted-foreground">
            Not a 10-digit US number, so it will be shown to copy rather than dialled.
          </p>
        )}
        {add.isError && (
          <p role="alert" className="text-sm text-danger">
            {add.error instanceof ApiError && add.error.status === 404
              ? 'Typed numbers can be saved once the server side of Calls is in place.'
              : `Could not save the number. ${add.error.message}`}
          </p>
        )}
        <Button type="submit" size="sm" disabled={!complete || add.isPending || onAdded === null}>
          {add.isPending ? 'Saving…' : 'Save and call'}
        </Button>
      </form>
    </Panel>
  )
}
