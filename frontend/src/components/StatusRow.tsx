import { CircleAlert, CircleCheck } from 'lucide-react'

type StatusRowProps = {
  label: string
  ok: boolean
  detail: string
}

export function StatusRow({ label, ok, detail }: StatusRowProps) {
  const Icon = ok ? CircleCheck : CircleAlert
  return (
    <div className="flex items-center gap-3 px-4 py-3">
      <Icon className={ok ? 'text-success' : 'text-warning'} aria-hidden />
      <dt className="w-40 font-medium">{label}</dt>
      <dd className="text-muted-foreground">{detail}</dd>
    </div>
  )
}
