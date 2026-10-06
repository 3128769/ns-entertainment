import { computed, reactive } from 'vue'
import { api, ApiError } from './api'
import { collectIssues } from './account'
import { describe } from './messages'
import { toast } from './toast'
import type { Account, Bot, Proxy, RunRecord, RunResult, WorkerState } from './types'

const POLL_MS = 30_000
const STALE_MS = 15_000

interface State {
  accounts: Account[]
  proxies: Proxy[]
  bots: Bot[]
  worker: WorkerState | null
  recent: { checkin: RunRecord[]; monitor: RunRecord[]; message: RunRecord[] }
  loaded: boolean
  loading: boolean
  error: string
  updatedAt: number
  /** Keys of actions in flight, e.g. `checkin:<accountId>`. */
  pending: Record<string, true>
}

export const store = reactive<State>({
  accounts: [],
  proxies: [],
  bots: [],
  worker: null,
  recent: { checkin: [], monitor: [], message: [] },
  loaded: false,
  loading: false,
  error: '',
  updatedAt: 0,
  pending: {},
})

export const issues = computed(() => collectIssues(store.accounts, store.worker, store.updatedAt || Date.now()))

let inflight: Promise<void> | null = null

/** Reload everything the pages show. Concurrent calls share one request. */
export function refresh(): Promise<void> {
  if (inflight) return inflight
  store.loading = true
  inflight = (async () => {
    try {
      const [accounts, proxies, bots, worker, checkin, monitor, message] = await Promise.all([
        api.accounts(), api.proxies(), api.bots(), api.workerState(),
        api.history('checkin', { limit: 100 }), api.history('monitor', { limit: 10 }), api.history('message', { limit: 10 }),
      ])
      store.accounts = accounts.items
      store.proxies = proxies.items
      store.bots = bots.items
      store.worker = worker
      store.recent = { checkin: checkin.items, monitor: monitor.items, message: message.items }
      store.error = ''
      store.loaded = true
      store.updatedAt = Date.now()
    } catch (error) {
      if (!(error instanceof ApiError && error.code === 'UNAUTHORIZED')) store.error = describe(error instanceof ApiError ? error.code : 'REQUEST_FAILED')
    } finally {
      store.loading = false
      inflight = null
    }
  })()
  return inflight
}

let timer: number | undefined
let onVisible: (() => void) | undefined

export function startPolling(): void {
  stopPolling()
  timer = window.setInterval(() => {
    if (document.visibilityState === 'visible') void refresh()
  }, POLL_MS)
  onVisible = () => {
    if (document.visibilityState === 'visible' && Date.now() - store.updatedAt > STALE_MS) void refresh()
  }
  document.addEventListener('visibilitychange', onVisible)
}

export function stopPolling(): void {
  if (timer !== undefined) window.clearInterval(timer)
  if (onVisible) document.removeEventListener('visibilitychange', onVisible)
  timer = undefined
  onVisible = undefined
}

export function resetStore(): void {
  store.accounts = []
  store.proxies = []
  store.bots = []
  store.worker = null
  store.recent = { checkin: [], monitor: [], message: [] }
  store.loaded = false
  store.error = ''
  store.updatedAt = 0
}

export function errorText(error: unknown): string {
  return describe(error instanceof ApiError ? error.code : 'REQUEST_FAILED')
}

const FAILURE = new Set(['failed', 'timeout', 'notify_failed', 'uncertain'])

/**
 * Run an action with a busy flag and a toast. Returns true when it succeeded.
 * `key` identifies the action so buttons can show their own spinner.
 */
export async function perform<T extends RunResult | { success?: boolean }>(
  key: string,
  action: () => Promise<T>,
  doneText: string,
): Promise<boolean> {
  if (store.pending[key]) return false
  store.pending[key] = true
  try {
    const result = await action()
    const failed = 'status' in result ? FAILURE.has(String((result as RunResult).status)) || result.success === false : result.success === false
    const text = 'message' in result && (result as RunResult).message ? describe((result as RunResult).message) : doneText
    if (failed) toast.error(text)
    else toast.ok(text)
    void refresh()
    return !failed
  } catch (error) {
    toast.error(errorText(error))
    return false
  } finally {
    delete store.pending[key]
  }
}

export const isPending = (key: string): boolean => !!store.pending[key]

/** One-click actions used by several pages. */
export const actions = {
  checkin: (a: Account) => perform(`checkin:${a.id}`, () => api.runCheckin(a.id), '签到已完成'),
  keywordCheck: (a: Account) => perform(`keyword:${a.id}`, () => api.runKeywordCheck(a.id), '关键词检查完成'),
  messageCheck: (a: Account) => perform(`message:${a.id}`, () => api.runMessageCheck(a.id), '私信检查完成'),
  testProxy: (p: Proxy) => perform(`proxy:${p.id}`, () => api.testProxy(p.id), '代理连接正常'),
}
