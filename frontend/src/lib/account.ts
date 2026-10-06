import { describe, statusInfo, type Tone } from './messages'
import { beijingDay, isToday, toDate } from './time'
import type { Account, Bot, Proxy, WorkerState } from './types'

// --- cookie ---------------------------------------------------------------------------------

export type CookieKey = 'valid' | 'expired' | 'blocked' | 'unknown' | 'missing'

export interface CookieState {
  key: CookieKey
  label: string
  tone: Tone
}

const EXPIRED_MARKERS = ['auth_expired', 'cookie_expired']

/** What we can say about an account's cookie from the results recorded so far. */
export function cookieState(a: Account): CookieState {
  const seen = [
    a.last_offline_status, a.last_offline_message, a.last_status, a.last_message,
    a.last_monitor_status, a.last_monitor_message, a.last_message_monitor_status, a.last_message_monitor_message,
  ].map((v) => String(v ?? '').toLowerCase())

  const expired =
    a.last_offline_status === 'notified' ||
    seen.some((v) => v === 'expired' || EXPIRED_MARKERS.some((marker) => v.includes(marker)))
  if (expired) return { key: 'expired', label: 'Cookie 已过期', tone: 'bad' }

  if (a.last_offline_status === 'failed') {
    return a.last_offline_message === 'NODESEEK_CLOUDFLARE_BLOCKED'
      ? { key: 'blocked', label: '访问受阻', tone: 'info' }
      : { key: 'unknown', label: '待确认', tone: 'muted' }
  }
  if (
    a.last_offline_status === 'ok' ||
    a.last_offline_message === 'NODESEEK_COOKIE_OK' ||
    a.last_status === 'success' ||
    a.last_status === 'already'
  ) {
    return { key: 'valid', label: 'Cookie 有效', tone: 'ok' }
  }
  return a.cookie_set ? { key: 'unknown', label: '待确认', tone: 'muted' } : { key: 'missing', label: '未配置', tone: 'bad' }
}

// --- schedule -------------------------------------------------------------------------------

export function scheduleLabel(a: Pick<Account, 'schedule_mode' | 'schedule_time' | 'schedule_start' | 'schedule_end'>): string {
  return a.schedule_mode === 'range' ? `${a.schedule_start}–${a.schedule_end} 随机` : a.schedule_time
}

function minutesOf(clock: string): number {
  const [hour, minute] = clock.split(':').map(Number)
  return (hour ?? 0) * 60 + (minute ?? 0)
}

function beijingMinutes(now: number): number {
  const date = toDate(now)
  if (!date) return 0
  const [hour, minute] = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(date).split(':').map(Number)
  return ((hour ?? 0) % 24) * 60 + (minute ?? 0)
}

// --- per-task health -------------------------------------------------------------------------

export type TaskKind = 'checkin' | 'keyword' | 'message' | 'cookie'
export type HealthState = 'off' | 'idle' | 'ok' | 'warn' | 'bad'

export interface TaskHealth {
  state: HealthState
  label: string
  at: string | null
}

const TASK_FIELDS: Record<TaskKind, { enabled: keyof Account; status: keyof Account; at: keyof Account }> = {
  checkin: { enabled: 'enabled', status: 'last_status', at: 'last_run_at' },
  keyword: { enabled: 'keyword_monitor_enabled', status: 'last_monitor_status', at: 'last_monitor_at' },
  message: { enabled: 'message_monitor_enabled', status: 'last_message_monitor_status', at: 'last_message_monitor_at' },
  cookie: { enabled: 'offline_notify_enabled', status: 'last_offline_status', at: 'last_offline_at' },
}

export function taskHealth(a: Account, kind: TaskKind): TaskHealth {
  const fields = TASK_FIELDS[kind]
  if (!a[fields.enabled]) return { state: 'off', label: kind === 'checkin' ? '已暂停' : '未启用', at: null }
  const status = a[fields.status] as string | null
  const at = a[fields.at] as string | null
  if (!status) return { state: 'idle', label: '等待首次执行', at: null }
  const info = statusInfo(status)
  const state: HealthState = info.tone === 'bad' ? 'bad' : 'ok'
  // Tiles are narrow: "Cookie 已过期" is shown as "已过期" (the account card has the full text).
  return { state, label: info.label.replace(/^Cookie /, ''), at }
}

export function checkedInToday(a: Account, now: number = Date.now()): boolean {
  return (a.last_status === 'success' || a.last_status === 'already') && isToday(a.last_run_at, now)
}

// --- things that need attention ----------------------------------------------------------------

export interface Issue {
  id: string
  severity: 'bad' | 'warn'
  title: string
  detail: string
  accountId?: string
  /** Drawer tab that fixes it. */
  tab?: 'basic' | 'schedule' | 'keywords' | 'messages' | 'alerts'
}

const GRACE_MINUTES = 30

function missedToday(a: Account, now: number): boolean {
  if (!a.enabled || checkedInToday(a, now) || a.last_status === 'uncertain') return false
  const due = minutesOf(a.schedule_mode === 'range' ? a.schedule_end : a.schedule_time)
  if (a.schedule_mode === 'range' && minutesOf(a.schedule_end) <= minutesOf(a.schedule_start)) return false // window spans midnight
  return beijingMinutes(now) >= due + GRACE_MINUTES && beijingDay(a.created_at || 0) !== beijingDay(now)
}

export function collectIssues(accounts: Account[], worker: WorkerState | null, now: number = Date.now()): Issue[] {
  const issues: Issue[] = []
  if (worker && !worker.ready) {
    issues.push({
      id: 'worker', severity: 'bad', title: '后台任务服务未运行',
      detail: '签到与监听已暂停，手动执行也无法完成。请检查 worker 容器是否在运行。',
    })
  }
  for (const a of accounts) {
    const cookie = cookieState(a)
    if (cookie.key === 'expired') {
      issues.push({ id: `cookie:${a.id}`, severity: 'bad', title: `${a.name} 的 Cookie 已过期`, detail: '重新登录 NodeSeek 后更新 Cookie，签到和私信检查才会恢复。', accountId: a.id, tab: 'basic' })
    }
    if (a.last_status === 'uncertain') {
      issues.push({ id: `uncertain:${a.id}`, severity: 'warn', title: `${a.name} 的签到结果待核实`, detail: '请求可能已经成功。请先到 NodeSeek 确认，系统不会自动重复签到。', accountId: a.id })
    } else if (cookie.key === 'expired') {
      // the cookie issue above already explains every sign-in problem
    } else if (a.enabled && ['failed', 'nodeseek_connect_failed'].includes(a.last_status ?? '')) {
      issues.push({ id: `checkin:${a.id}`, severity: 'warn', title: `${a.name} 上次签到失败`, detail: describe(a.last_message), accountId: a.id })
    } else if (missedToday(a, now)) {
      issues.push({ id: `missed:${a.id}`, severity: 'warn', title: `${a.name} 今天还没有签到`, detail: `计划时间 ${scheduleLabel(a)} 已过。`, accountId: a.id, tab: 'schedule' })
    }
    if (a.keyword_monitor_enabled && ['failed', 'notify_failed'].includes(a.last_monitor_status ?? '')) {
      issues.push({ id: `keywords:${a.id}`, severity: 'warn', title: `${a.name} 的关键词监听异常`, detail: describe(a.last_monitor_message), accountId: a.id, tab: 'keywords' })
    }
    if (a.message_monitor_enabled && ['failed', 'notify_failed'].includes(a.last_message_monitor_status ?? '') && cookie.key !== 'expired') {
      issues.push({ id: `messages:${a.id}`, severity: 'warn', title: `${a.name} 的私信监听异常`, detail: describe(a.last_message_monitor_message), accountId: a.id, tab: 'messages' })
    }
  }
  return issues.sort((x, y) => (x.severity === y.severity ? 0 : x.severity === 'bad' ? -1 : 1))
}

// --- lookups --------------------------------------------------------------------------------

export function botName(bots: Bot[], id: string | null): string {
  return bots.find((bot) => bot.id === id)?.name ?? (id ? '已删除的 Bot' : '未选择')
}

export function proxyName(proxies: Proxy[], id: string | null): string {
  return proxies.find((proxy) => proxy.id === id)?.name ?? (id ? '已删除的代理' : '直连')
}

/** Accounts that route notifications through the given bot. */
export function botUsage(accounts: Account[], botId: string): number {
  return accounts.filter((a) =>
    [a.keyword_bot_id, a.message_bot_id, a.offline_bot_id].includes(botId) &&
    ((a.keyword_bot_id === botId && a.keyword_monitor_enabled) ||
      (a.message_bot_id === botId && a.message_monitor_enabled) ||
      (a.offline_bot_id === botId && a.offline_notify_enabled)),
  ).length
}
