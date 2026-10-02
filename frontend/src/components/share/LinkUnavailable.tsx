/** Shown for an unknown, expired, or withdrawn link: a plain message and nothing else. */
export function LinkUnavailable({ expired }: { expired: boolean }) {
  return (
    <div role="status">
      <h1 className="font-serif text-2xl">This link is not available</h1>
      <p className="mt-3 text-sm text-muted-foreground">
        {expired ? 'It has expired or was withdrawn by the law firm.' : 'The address is not a valid case status link.'}{' '}
        Contact the law firm that sent it for a new one.
      </p>
    </div>
  )
}
