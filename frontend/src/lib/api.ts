import { auth, clearToken } from './auth'
import type {
  Account, AccountInput, Bot, BotInput, HistoryKind, Page, Proxy, ProxyInput, RunRecord, RunResult, WorkerState,
} from './types'

export class ApiError extends Error {
  constructor(
    readonly code: string,
    readonly status: number,
    readonly fields: string[] = [],
  ) {
    super(code)
  }
}

interface RequestOptions {
  /** Login must not treat its own 401 as "session expired". */
  anonymous?: boolean
}

async function request<T>(method: string, path: string, body?: unknown, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth.token && !options.anonymous) headers.Authorization = `Bearer ${auth.token}`

  let response: Response
  try {
    response = await fetch(`/api${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
  } catch {
    throw new ApiError('NETWORK_ERROR', 0)
  }
  const data = await response.json().catch(() => ({}))
  if (response.status === 401 && !options.anonymous) {
    clearToken()
    throw new ApiError('UNAUTHORIZED', 401)
  }
  if (!response.ok) {
    const code = typeof data.detail === 'string' ? data.detail : 'REQUEST_FAILED'
    throw new ApiError(code, response.status, Array.isArray(data.fields) ? data.fields : [])
  }
  return data as T
}

const HISTORY_PATH: Record<HistoryKind, string> = {
  checkin: '/history',
  monitor: '/monitor-history',
  message: '/message-history',
}

export interface HistoryQuery {
  limit?: number
  offset?: number
  account_id?: string
  status?: string
}

function queryString(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) if (value !== undefined && value !== '') search.set(key, String(value))
  const text = search.toString()
  return text ? `?${text}` : ''
}

export const api = {
  login: (username: string, password: string) =>
    request<{ access_token: string }>('POST', '/auth/login', { username, password }, { anonymous: true }),
  logout: () => request<{ success: boolean }>('POST', '/auth/logout'),

  accounts: () => request<Page<Account>>('GET', '/accounts'),
  createAccount: (input: AccountInput) => request<{ account: Account }>('POST', '/accounts', input),
  updateAccount: (id: string, patch: AccountInput) => request<{ account: Account }>('PATCH', `/accounts/${id}`, patch),
  deleteAccount: (id: string) => request<{ success: boolean }>('DELETE', `/accounts/${id}`),
  runCheckin: (id: string) => request<RunResult>('POST', `/accounts/${id}/run`),
  runKeywordCheck: (id: string) => request<RunResult>('POST', `/accounts/${id}/monitor/run`),
  runMessageCheck: (id: string) => request<RunResult>('POST', `/accounts/${id}/messages/run`),

  proxies: () => request<Page<Proxy>>('GET', '/proxies'),
  createProxy: (input: ProxyInput) => request<{ proxy: Proxy }>('POST', '/proxies', input),
  updateProxy: (id: string, patch: ProxyInput) => request<{ proxy: Proxy }>('PATCH', `/proxies/${id}`, patch),
  deleteProxy: (id: string) => request<{ success: boolean }>('DELETE', `/proxies/${id}`),
  testProxy: (id: string) => request<RunResult & { latency_ms: number | null }>('POST', `/proxies/${id}/test`),

  bots: () => request<{ items: Bot[] }>('GET', '/bots'),
  saveBot: (input: BotInput) => request<{ bot: Bot }>('POST', '/bots', input),
  deleteBot: (id: string) => request<{ success: boolean }>('DELETE', `/bots/${id}`),
  testBot: (id: string) => request<RunResult>('POST', `/bots/${id}/test`),

  history: (kind: HistoryKind, query: HistoryQuery = {}) =>
    request<Page<RunRecord>>('GET', HISTORY_PATH[kind] + queryString({ limit: 20, ...query })),

  workerState: () => request<WorkerState>('GET', '/system/tasks'),
}
