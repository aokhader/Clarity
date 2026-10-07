export class ApiError extends Error {
  readonly status: number
  /** The error body's `detail`, when it sent one; a structured refusal carries its reasons here. */
  readonly detail: unknown

  constructor(status: number, message: string, detail: unknown = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

/** The `detail` of an error response, if its body is JSON that has one. */
export async function errorDetail(response: Response): Promise<unknown> {
  try {
    const body: unknown = await response.json()
    return typeof body === 'object' && body !== null && 'detail' in body ? body.detail : null
  } catch {
    return null
  }
}

type RequestOptions = {
  /** The stub firm user, sent as X-User-Id. Provider routes never need it. */
  userId?: number
}

function headersFor({ userId }: RequestOptions): Record<string, string> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (userId !== undefined) headers['X-User-Id'] = String(userId)
  return headers
}

async function readJson<T>(response: Response, url: string): Promise<T> {
  if (!response.ok) {
    throw new ApiError(response.status, `${response.status} ${response.statusText} from ${url}`, await errorDetail(response))
  }
  const body: unknown = await response.json()
  // The shape is guaranteed by the backend's response schemas, which types.ts mirrors.
  return body as T
}

/** GET a JSON resource under /api. Vite proxies /api to the FastAPI server. */
export async function apiGet<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = `/api${path}`
  return readJson<T>(await fetch(url, { headers: headersFor(options) }), url)
}

async function apiSend<T>(method: 'POST' | 'PUT', path: string, options: RequestOptions, body?: unknown): Promise<T> {
  const url = `/api${path}`
  const headers = headersFor(options)
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const init: RequestInit = { method, headers }
  if (body !== undefined) init.body = JSON.stringify(body)
  return readJson<T>(await fetch(url, init), url)
}

/** POST to /api, with an optional JSON body. */
export function apiPost<T>(path: string, options: RequestOptions = {}, body?: unknown): Promise<T> {
  return apiSend<T>('POST', path, options, body)
}

/** PUT a JSON body to /api, replacing the resource. */
export function apiPut<T>(path: string, options: RequestOptions = {}, body?: unknown): Promise<T> {
  return apiSend<T>('PUT', path, options, body)
}
