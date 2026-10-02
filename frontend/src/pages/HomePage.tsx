import { BackendStatus } from '@/components/BackendStatus'

export function HomePage() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <h1 className="font-serif text-3xl">Clarity</h1>
      <p className="mt-2 text-muted-foreground">
        Setup status. Once Clio credentials are set, run <code>python -m app.cli sync</code> from{' '}
        <code>backend/</code>.
      </p>
      <section className="mt-8" aria-label="Setup status">
        <BackendStatus />
      </section>
    </main>
  )
}
