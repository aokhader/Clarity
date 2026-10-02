import { useFirmUser } from '@/api/users'
import { ProvidersPanel } from '@/components/share/ProvidersPanel'

/** Track C's providers panel, acting as the firm user chosen in the switcher. */
export function ProvidersSection({ matterId }: { matterId: number }) {
  const user = useFirmUser()
  return <ProvidersPanel matterId={matterId} userId={user?.id ?? null} />
}
