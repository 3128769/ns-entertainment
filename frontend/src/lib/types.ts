export type ScheduleMode = 'fixed' | 'range'

export interface Account {
  id: string
  name: string
  enabled: boolean
  random_checkin: boolean
  schedule_mode: ScheduleMode
  schedule_time: string
  schedule_start: string
  schedule_end: string
  proxy_id: string | null
  user_agent: string
  keyword_monitor_enabled: boolean
  keywords: string[]
  keyword_bot_id: string | null
  keyword_chat_id: string | null
  message_monitor_enabled: boolean
  message_bot_id: string | null
  message_chat_id: string | null
  offline_notify_enabled: boolean
  offline_bot_id: string | null
  offline_chat_id: string | null
  last_status: string | null
  last_message: string | null
  last_run_at: string | null
  last_monitor_status: string | null
  last_monitor_message: string | null
  last_monitor_at: string | null
  last_match_at: string | null
  last_message_monitor_status: string | null
  last_message_monitor_message: string | null
  last_message_monitor_at: string | null
  last_offline_status: string | null
  last_offline_message: string | null
  last_offline_at: string | null
  created_at: string
  updated_at: string
  cookie_set: boolean
}

/** Fields accepted when creating or editing an account (cookie is write-only). */
export type AccountInput = Partial<
  Omit<Account, 'id' | 'cookie_set' | 'created_at' | 'updated_at' | `last_${string}`>
> & { cookie?: string }

export interface Proxy {
  id: string
  name: string
  protocol: string
  host: string
  port: number
  remark: string
  assigned_count: number
  last_test_success: boolean | null
  last_test_latency_ms: number | null
  last_tested_at: string | null
  last_test_code: string | null
  created_at: string
  updated_at: string
}

export interface ProxyInput {
  name?: string
  remark?: string
  proxy_url?: string
}

export interface Bot {
  id: string
  name: string
  username: string
  enabled: boolean
  chat_id: string | null
}

export interface BotInput {
  name: string
  token: string
  chat_id: string
  bot_id?: string
}

export type HistoryKind = 'checkin' | 'monitor' | 'message'

export interface RunRecord {
  success: boolean
  status: string
  message: string
  account_id: string
  account_name: string
  source: 'manual' | 'scheduled' | string
  ran_at: string
  gained?: number | null
  checked?: number
  new_posts?: number
  new_messages?: number
  matched?: number
  notified?: boolean
}

export interface Page<T> {
  items: T[]
  total: number
}

export interface JobSummary {
  id: number
  account_id: string
  job_type: string
  status: string
  attempts: number
  started_at: string | null
  finished_at: string | null
  last_error: string | null
}

export interface WorkerState {
  ready: boolean
  heartbeat_at: string | null
  concurrency: number | null
  counts: Record<string, number>
  oldest_queued_at: string | null
  recent_jobs: JobSummary[]
  version: string
}

export interface RunResult {
  success: boolean
  status: string
  message: string
}
