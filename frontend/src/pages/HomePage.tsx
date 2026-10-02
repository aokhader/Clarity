import { BackendStatus } from '@/components/BackendStatus'
import { MatterList } from '@/components/firm/MatterList'

export function HomePage() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <h1 className="font-serif text-3xl">Clarity</h1>
      <p className="mt-2 text-muted-foreground">
        Every matter synced from Clio, digested into sourced facts.
      </p>
      <div className="mt-8 space-y-6">
        <MatterList />
        <section aria-label="Setup status">
          <BackendStatus />
        </section>
      </div>
    </main>
  )
}
