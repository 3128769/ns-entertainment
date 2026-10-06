import { describe, expect, it } from 'vitest'
import { botUsage, checkedInToday, collectIssues, cookieState, scheduleLabel, taskHealth } from './account'
import { makeAccount } from './fixtures'
import type { WorkerState } from './types'

const NOW = Date.parse('2026-10-06T12:00:00Z') // 20:00 Beijing

describe('cookieState', () => {
  it('is valid after a successful check-in or an ok cookie check', () => {
    expect(cookieState(makeAccount({ last_status: 'success' })).key).toBe('valid')
    expect(cookieState(makeAccount({ last_status: 'already' })).key).toBe('valid')
    expect(cookieState(makeAccount({ last_offline_status: 'ok' })).key).toBe('valid')
  })

  it('is expired when any task reported it, or the alert went out', () => {
    expect(cookieState(makeAccount({ last_status: 'nodeseek_auth_expired' })).key).toBe('expired')
    expect(cookieState(makeAccount({ last_message_monitor_message: 'NODESEEK_AUTH_EXPIRED' })).key).toBe('expired')
    expect(cookieState(makeAccount({ last_offline_status: 'notified' })).key).toBe('expired')
  })

  it('treats a blocked check as unknown rather than expired', () => {
    const state = cookieState(makeAccount({ last_offline_status: 'failed', last_offline_message: 'NODESEEK_CLOUDFLARE_BLOCKED' }))
    expect(state).toMatchObject({ key: 'blocked', tone: 'info' })
  })

  it('distinguishes "not checked yet" from "no cookie"', () => {
    expect(cookieState(makeAccount()).key).toBe('unknown')
    expect(cookieState(makeAccount({ cookie_set: false })).key).toBe('missing')
  })
})

describe('taskHealth', () => {
  it('reports disabled tasks as off and untouched ones as waiting', () => {
    expect(taskHealth(makeAccount({ enabled: false }), 'checkin')).toMatchObject({ state: 'off', label: '已暂停' })
    expect(taskHealth(makeAccount(), 'keyword')).toMatchObject({ state: 'off', label: '未启用' })
    expect(taskHealth(makeAccount({ keyword_monitor_enabled: true }), 'keyword').state).toBe('idle')
  })

  it('maps results to ok/bad and keeps tiles short', () => {
    expect(taskHealth(makeAccount({ last_status: 'success', last_run_at: 'x' }), 'checkin').state).toBe('ok')
    expect(taskHealth(makeAccount({ last_monitor_status: 'no_match', keyword_monitor_enabled: true }), 'keyword').state).toBe('ok')
    const expired = taskHealth(makeAccount({ last_status: 'nodeseek_auth_expired' }), 'checkin')
    expect(expired).toMatchObject({ state: 'bad', label: '已过期' })
    expect(taskHealth(makeAccount({ last_status: 'uncertain' }), 'checkin').state).toBe('bad')
  })
})

describe('schedule helpers', () => {
  it('labels fixed and range schedules', () => {
    expect(scheduleLabel(makeAccount())).toBe('08:20')
    expect(scheduleLabel(makeAccount({ schedule_mode: 'range', schedule_start: '07:30', schedule_end: '09:00' }))).toBe('07:30–09:00 随机')
  })

  it('knows whether today is done in Beijing time', () => {
    expect(checkedInToday(makeAccount({ last_status: 'success', last_run_at: '2026-10-06T00:30:00Z' }), NOW)).toBe(true)
    expect(checkedInToday(makeAccount({ last_status: 'success', last_run_at: '2026-10-05T00:30:00Z' }), NOW)).toBe(false)
    expect(checkedInToday(makeAccount({ last_status: 'failed', last_run_at: '2026-10-06T00:30:00Z' }), NOW)).toBe(false)
    // 23:30 UTC on the 5th is already the 6th in Beijing
    expect(checkedInToday(makeAccount({ last_status: 'success', last_run_at: '2026-10-05T23:30:00Z' }), NOW)).toBe(true)
  })
})

describe('collectIssues', () => {
  const worker = (ready: boolean): WorkerState => ({ ready, heartbeat_at: null, concurrency: 4, counts: {}, oldest_queued_at: null, recent_jobs: [], version: '3' })

  it('puts a stopped worker first and an expired cookie before warnings', () => {
    const accounts = [
      makeAccount({ id: 'u', name: '待核实', last_status: 'uncertain', last_run_at: '2026-10-06T00:30:00Z' }),
      makeAccount({ id: 'e', name: '过期', last_status: 'nodeseek_auth_expired', last_run_at: '2026-10-06T00:30:00Z' }),
    ]
    const issues = collectIssues(accounts, worker(false), NOW)
    expect(issues.map((i) => i.id)).toEqual(['worker', 'cookie:e', 'uncertain:u'])
    expect(issues[0]?.severity).toBe('bad')
  })

  it('flags a check-in that is overdue but not one that is still upcoming or already done', () => {
    const missed = makeAccount({ id: 'm', schedule_time: '08:20' })
    const upcoming = makeAccount({ id: 'f', schedule_time: '23:30' })
    const done = makeAccount({ id: 'd', last_status: 'success', last_run_at: '2026-10-06T00:30:00Z' })
    const fresh = makeAccount({ id: 'n', created_at: '2026-10-06T11:00:00Z' }) // created after the time passed today
    const ids = collectIssues([missed, upcoming, done, fresh], worker(true), NOW).map((i) => i.id)
    expect(ids).toEqual(['missed:m'])
  })

  it('shows readable text for monitor failures, never the raw code', () => {
    const a = makeAccount({ keyword_monitor_enabled: true, last_monitor_status: 'notify_failed', last_monitor_message: 'TELEGRAM_CHAT_FORBIDDEN', last_status: 'success', last_run_at: '2026-10-06T00:30:00Z' })
    const [issue] = collectIssues([a], worker(true), NOW)
    expect(issue?.detail).toContain('Bot 无权发送通知')
  })
})

describe('botUsage', () => {
  it('counts only features that are switched on', () => {
    const accounts = [
      makeAccount({ keyword_bot_id: 'b', keyword_monitor_enabled: true }),
      makeAccount({ id: '2', message_bot_id: 'b', message_monitor_enabled: false }),
      makeAccount({ id: '3', offline_bot_id: 'b', offline_notify_enabled: true }),
    ]
    expect(botUsage(accounts, 'b')).toBe(2)
  })
})
