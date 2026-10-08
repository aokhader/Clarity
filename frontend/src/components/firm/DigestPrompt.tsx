export function DigestPrompt() {
  return (
    <div className="rounded-lg border bg-card px-5 py-4 text-sm">
      <p className="font-medium">This matter is synced but not digested yet.</p>
      <p className="mt-1 text-muted-foreground">
        Run <code>python -m app.cli digest</code> from <code>backend/</code> to build the facts and the brief.
      </p>
    </div>
  )
}
