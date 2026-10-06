import { reactive } from 'vue'

export type ToastTone = 'ok' | 'bad' | 'info'

export interface ToastItem {
  id: number
  tone: ToastTone
  text: string
}

export const toasts = reactive<ToastItem[]>([])
let nextId = 1

function push(tone: ToastTone, text: string, ms: number): void {
  const id = nextId++
  toasts.push({ id, tone, text })
  setTimeout(() => dismiss(id), ms)
}

export function dismiss(id: number): void {
  const index = toasts.findIndex((t) => t.id === id)
  if (index >= 0) toasts.splice(index, 1)
}

export const toast = {
  ok: (text: string) => push('ok', text, 3500),
  info: (text: string) => push('info', text, 4000),
  error: (text: string) => push('bad', text, 7000),
}
