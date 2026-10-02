export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** GET a JSON resource under /api. Vite proxies /api to the FastAPI server. */
export async function apiGet<T>(path: string): Promise<T> {
  const url = `/api${path}`
  const response = await fetch(url, { headers: { Accept: 'application/json' } })
  if (!response.ok) {
    throw new ApiError(response.status, `${response.status} ${response.statusText} from ${url}`)
  }
  const body: unknown = await response.json()
  // The shape is guaranteed by the backend's response schemas, which types.ts mirrors.
  return body as T
}
