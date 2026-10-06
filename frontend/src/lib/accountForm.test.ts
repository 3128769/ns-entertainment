import { describe, expect, it } from 'vitest'
import { blankForm, buildPayload, formFrom, hasChanges, validateForm } from './accountForm'
import { makeAccount } from './fixtures'

describe('buildPayload', () => {
  it('sends everything when creating', () => {
    const form = { ...blankForm(), name: ' 新账号 ', cookie: ' a=b ' }
    const payload = buildPayload(form)
    expect(payload).toMatchObject({ name: '新账号', cookie: 'a=b', schedule_mode: 'fixed', keywords: [], proxy_id: null })
  })

  it('sends only what changed when editing', () => {
    const account = makeAccount({ keywords: ['a'] })
    const form = formFrom(account)
    expect(buildPayload(form, account)).toEqual({})
    form.name = '改名'
    form.keywords = ['a', 'b']
    expect(buildPayload(form, account)).toEqual({ name: '改名', keywords: ['a', 'b'] })
  })

  it('treats empty selects as null and does not resend an unchanged cookie', () => {
    const account = makeAccount({ proxy_id: 'p1' })
    const form = formFrom(account)
    form.proxy_id = ''
    expect(buildPayload(form, account)).toEqual({ proxy_id: null })
    form.proxy_id = 'p1'
    form.cookie = 'new=1'
    expect(buildPayload(form, account)).toEqual({ cookie: 'new=1' })
  })

  it('reports whether there is anything to save', () => {
    const account = makeAccount()
    const form = formFrom(account)
    expect(hasChanges(form, account)).toBe(false)
    form.random_checkin = false
    expect(hasChanges(form, account)).toBe(true)
  })
})

describe('validateForm', () => {
  it('requires a name and, when creating, a cookie', () => {
    const { fields, tabs } = validateForm(blankForm(), 'create')
    expect(fields.name).toBeTruthy()
    expect(fields.cookie).toBeTruthy()
    expect(tabs.basic).toBe(true)
    expect(validateForm({ ...blankForm(), name: 'x' }, 'edit').fields.cookie).toBeUndefined()
  })

  it('rejects a malformed cookie and an empty time window', () => {
    const form = { ...blankForm(), name: 'x', cookie: 'nocookie', schedule_mode: 'range' as const, schedule_start: '09:00', schedule_end: '09:00' }
    const { fields, tabs } = validateForm(form, 'create')
    expect(fields.cookie).toContain('Cookie 格式')
    expect(fields.schedule_end).toBeTruthy()
    expect(tabs.schedule).toBe(true)
  })

  it('only demands bot and chat for features that are switched on', () => {
    const base = { ...blankForm(), name: 'x', cookie: 'a=b' }
    expect(validateForm(base, 'create').fields).toEqual({})
    const kw = validateForm({ ...base, keyword_monitor_enabled: true }, 'create')
    expect(Object.keys(kw.fields).sort()).toEqual(['keyword_bot_id', 'keyword_chat_id', 'keywords'])
    expect(kw.tabs.keywords).toBe(true)
    const off = validateForm({ ...base, offline_notify_enabled: true, offline_bot_id: 'b', offline_chat_id: '1' }, 'create')
    expect(off.fields).toEqual({})
  })
})
