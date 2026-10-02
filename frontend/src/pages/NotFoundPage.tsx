import { Link } from 'react-router'

export function NotFoundPage() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <h1 className="font-serif text-3xl">Page not found</h1>
      <Link to="/" className="mt-4 inline-block text-primary underline-offset-4 hover:underline">
        Back to the start
      </Link>
    </main>
  )
}
