import { useParams } from 'react-router'

export function MatterPage() {
  const { matterId } = useParams()
  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <h1 className="font-serif text-3xl">Matter {matterId}</h1>
      <p className="mt-2 text-muted-foreground">The firm view is not built yet (Track B).</p>
    </main>
  )
}
