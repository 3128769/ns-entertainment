/** All times are shown in Beijing time, the zone the schedules are defined in. */
const ZONE = 'Asia/Shanghai'

const parts = new Intl.DateTimeFormat('en-GB', {
  timeZone: ZONE, year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
})

function fields(date: Date): Record<string, string> {
  const out: Record<string, string> = {}
  for (const part of parts.formatToParts(date)) out[part.type] = part.value
  if (out.hour === '24') out.hour = '00'
  return out
}

export function toDate(value: string | number | Date | null | undefined): Date | null {
  if (value === null || value === undefined || value === '') return null
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

/** `10-06 20:15` */
export function formatTime(value: string | null | undefined): string {
  const date = toDate(value)
  if (!date) return '--'
  const f = fields(date)
  return `${f.month}-${f.day} ${f.hour}:${f.minute}`
}

/** `2026-10-06 20:15:30` for tooltips. */
export function formatFull(value: string | null | undefined): string {
  const date = toDate(value)
  if (!date) return ''
  const f = fields(date)
  return `${f.year}-${f.month}-${f.day} ${f.hour}:${f.minute}:${f.second}（北京时间）`
}

/** `2026-10-06` in Beijing time. */
export function beijingDay(value: string | number | Date): string {
  const date = toDate(value)
  if (!date) return ''
  const f = fields(date)
  return `${f.year}-${f.month}-${f.day}`
}

export function isToday(value: string | null | undefined, now: number = Date.now()): boolean {
  const date = toDate(value)
  return !!date && beijingDay(date) === beijingDay(now)
}

/** `刚刚` / `5 分钟前` / `3 小时前` / `昨天 20:15` / `10-04 08:20` */
export function relativeTime(value: string | null | undefined, now: number = Date.now()): string {
  const date = toDate(value)
  if (!date) return '--'
  const seconds = Math.round((now - date.getTime()) / 1000)
  if (seconds < -60) return formatTime(value)
  if (seconds < 45) return '刚刚'
  if (seconds < 3600) return `${Math.max(1, Math.round(seconds / 60))} 分钟前`
  if (seconds < 6 * 3600) return `${Math.round(seconds / 3600)} 小时前`
  const day = beijingDay(date)
  if (day === beijingDay(now)) return `今天 ${formatTime(value).slice(6)}`
  if (day === beijingDay(now - 86400000)) return `昨天 ${formatTime(value).slice(6)}`
  return formatTime(value)
}
