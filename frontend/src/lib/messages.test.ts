import { describe as suite, expect, it } from 'vitest'
import { describe, statusInfo } from './messages'
import { beijingDay, formatTime, isToday, relativeTime } from './time'

suite('messages', () => {
  it('translates known codes and passes unknown text through', () => {
    expect(describe('NODESEEK_AUTH_EXPIRED')).toContain('Cookie 已过期')
    expect(describe('nodeseek_cloudflare_blocked')).toContain('访问受阻')
    expect(describe('今天的签到收益是4个鸡腿')).toBe('今天的签到收益是4个鸡腿')
    expect(describe(null)).toBe('等待执行')
    expect(describe('SOME_NEW_CODE')).toBe('SOME NEW CODE')
  })

  it('uses the previous interface\'s tones for statuses', () => {
    expect(statusInfo('success')).toEqual({ label: '成功', tone: 'ok' })
    expect(statusInfo('uncertain').tone).toBe('bad')
    expect(statusInfo('baseline').tone).toBe('info')
    expect(statusInfo(null)).toEqual({ label: '未执行', tone: 'muted' })
  })
})

suite('time (Beijing)', () => {
  it('formats and compares days in Beijing time, not the viewer\'s', () => {
    expect(formatTime('2026-10-06T12:05:00Z')).toBe('10-06 20:05')
    expect(formatTime('2026-10-05T16:30:00Z')).toBe('10-06 00:30')
    expect(beijingDay(Date.parse('2026-10-05T16:30:00Z'))).toBe('2026-10-06')
    expect(isToday('2026-10-05T16:30:00Z', Date.parse('2026-10-06T12:00:00Z'))).toBe(true)
    expect(formatTime(null)).toBe('--')
  })

  it('describes recent times relative to now', () => {
    const now = Date.parse('2026-10-06T12:00:00Z')
    expect(relativeTime('2026-10-06T11:59:50Z', now)).toBe('刚刚')
    expect(relativeTime('2026-10-06T11:30:00Z', now)).toBe('30 分钟前')
    expect(relativeTime('2026-10-06T09:00:00Z', now)).toBe('3 小时前')
    expect(relativeTime('2026-10-06T01:00:00Z', now)).toBe('今天 09:00')
    expect(relativeTime('2026-10-05T01:00:00Z', now)).toBe('昨天 09:00')
    expect(relativeTime('2026-09-01T01:00:00Z', now)).toBe('09-01 09:00')
  })
})
