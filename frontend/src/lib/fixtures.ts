import type { Account } from './types'

/** A complete account with everything off; tests override what they care about. */
export function makeAccount(overrides: Partial<Account> = {}): Account {
  return {
    id: 'a1', name: '测试', enabled: true, random_checkin: true,
    schedule_mode: 'fixed', schedule_time: '08:20', schedule_start: '08:20', schedule_end: '09:20',
    proxy_id: null, user_agent: 'UA',
    keyword_monitor_enabled: false, keywords: [], keyword_bot_id: null, keyword_chat_id: null,
    message_monitor_enabled: false, message_bot_id: null, message_chat_id: null,
    offline_notify_enabled: false, offline_bot_id: null, offline_chat_id: null,
    last_status: null, last_message: null, last_run_at: null,
    last_monitor_status: null, last_monitor_message: null, last_monitor_at: null, last_match_at: null,
    last_message_monitor_status: null, last_message_monitor_message: null, last_message_monitor_at: null,
    last_offline_status: null, last_offline_message: null, last_offline_at: null,
    created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', cookie_set: true,
    ...overrides,
  }
}
