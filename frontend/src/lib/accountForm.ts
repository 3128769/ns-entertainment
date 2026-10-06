import type { Account, AccountInput, ScheduleMode } from './types'

export type TabKey = 'basic' | 'schedule' | 'keywords' | 'messages' | 'alerts'

/** Editable copy of an account. Empty string means "not set" for every select/text field. */
export interface AccountForm {
  name: string
  enabled: boolean
  cookie: string
  proxy_id: string
  user_agent: string
  schedule_mode: ScheduleMode
  schedule_time: string
  schedule_start: string
  schedule_end: string
  random_checkin: boolean
  keyword_monitor_enabled: boolean
  keywords: string[]
  keyword_bot_id: string
  keyword_chat_id: string
  message_monitor_enabled: boolean
  message_bot_id: string
  message_chat_id: string
  offline_notify_enabled: boolean
  offline_bot_id: string
  offline_chat_id: string
}

export function blankForm(): AccountForm {
  return {
    name: '', enabled: true, cookie: '', proxy_id: '', user_agent: '',
    schedule_mode: 'fixed', schedule_time: '08:20', schedule_start: '08:20', schedule_end: '09:20', random_checkin: true,
    keyword_monitor_enabled: false, keywords: [], keyword_bot_id: '', keyword_chat_id: '',
    message_monitor_enabled: false, message_bot_id: '', message_chat_id: '',
    offline_notify_enabled: false, offline_bot_id: '', offline_chat_id: '',
  }
}

export function formFrom(a: Account): AccountForm {
  return {
    name: a.name, enabled: a.enabled, cookie: '', proxy_id: a.proxy_id ?? '', user_agent: a.user_agent ?? '',
    schedule_mode: a.schedule_mode, schedule_time: a.schedule_time, schedule_start: a.schedule_start, schedule_end: a.schedule_end,
    random_checkin: a.random_checkin,
    keyword_monitor_enabled: a.keyword_monitor_enabled, keywords: [...a.keywords], keyword_bot_id: a.keyword_bot_id ?? '', keyword_chat_id: a.keyword_chat_id ?? '',
    message_monitor_enabled: a.message_monitor_enabled, message_bot_id: a.message_bot_id ?? '', message_chat_id: a.message_chat_id ?? '',
    offline_notify_enabled: a.offline_notify_enabled, offline_bot_id: a.offline_bot_id ?? '', offline_chat_id: a.offline_chat_id ?? '',
  }
}

const NULLABLE = ['proxy_id', 'keyword_bot_id', 'keyword_chat_id', 'message_bot_id', 'message_chat_id', 'offline_bot_id', 'offline_chat_id'] as const
const PLAIN = [
  'name', 'enabled', 'user_agent', 'schedule_mode', 'schedule_time', 'schedule_start', 'schedule_end', 'random_checkin',
  'keyword_monitor_enabled', 'message_monitor_enabled', 'offline_notify_enabled',
] as const

/**
 * What to send to the API. Editing sends only the fields that changed, so saving
 * one tab can never overwrite something changed elsewhere in the meantime.
 */
export function buildPayload(form: AccountForm, original?: Account): AccountInput {
  const payload: Record<string, unknown> = {}
  const base = original ? formFrom(original) : null

  for (const key of PLAIN) {
    const value = typeof form[key] === 'string' ? (form[key] as string).trim() : form[key]
    if (!base || value !== base[key]) payload[key] = value
  }
  for (const key of NULLABLE) {
    const value = form[key].trim() || null
    if (!base || value !== (base[key].trim() || null)) payload[key] = value
  }
  if (!base || form.keywords.join('\n') !== base.keywords.join('\n')) payload.keywords = form.keywords
  if (form.cookie.trim()) payload.cookie = form.cookie.trim()
  return payload as AccountInput
}

export function hasChanges(form: AccountForm, original?: Account): boolean {
  return Object.keys(buildPayload(form, original)).length > 0
}

export interface FormErrors {
  fields: Partial<Record<keyof AccountForm, string>>
  tabs: Partial<Record<TabKey, true>>
}

const TAB_OF: Partial<Record<keyof AccountForm, TabKey>> = {
  name: 'basic', cookie: 'basic',
  schedule_start: 'schedule', schedule_end: 'schedule', schedule_time: 'schedule',
  keywords: 'keywords', keyword_bot_id: 'keywords', keyword_chat_id: 'keywords',
  message_bot_id: 'messages', message_chat_id: 'messages',
  offline_bot_id: 'alerts', offline_chat_id: 'alerts',
}

export function validateForm(form: AccountForm, mode: 'create' | 'edit'): FormErrors {
  const fields: FormErrors['fields'] = {}
  if (!form.name.trim()) fields.name = '请填写账号名称'
  const cookie = form.cookie.trim()
  if (mode === 'create' && !cookie) fields.cookie = '请粘贴完整的 Cookie'
  else if (cookie && !cookie.includes('=')) fields.cookie = 'Cookie 格式不对，应形如 name=value; name2=value2'
  if (form.schedule_mode === 'range' && form.schedule_start === form.schedule_end) fields.schedule_end = '开始与结束时间不能相同'
  if (form.schedule_mode === 'fixed' && !form.schedule_time) fields.schedule_time = '请选择签到时间'

  if (form.keyword_monitor_enabled) {
    if (!form.keywords.length) fields.keywords = '至少添加一个关键词'
    if (!form.keyword_bot_id) fields.keyword_bot_id = '请选择通知 Bot'
    if (!form.keyword_chat_id.trim()) fields.keyword_chat_id = '请填写接收人 Chat ID'
  }
  if (form.message_monitor_enabled) {
    if (!form.message_bot_id) fields.message_bot_id = '请选择通知 Bot'
    if (!form.message_chat_id.trim()) fields.message_chat_id = '请填写接收人 Chat ID'
  }
  if (form.offline_notify_enabled) {
    if (!form.offline_bot_id) fields.offline_bot_id = '请选择通知 Bot'
    if (!form.offline_chat_id.trim()) fields.offline_chat_id = '请填写接收人 Chat ID'
  }

  const tabs: FormErrors['tabs'] = {}
  for (const key of Object.keys(fields) as (keyof AccountForm)[]) {
    const tab = TAB_OF[key]
    if (tab) tabs[tab] = true
  }
  return { fields, tabs }
}
