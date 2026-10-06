import { reactive } from 'vue'

export interface ConfirmOptions {
  title: string
  message?: string
  confirmText?: string
  danger?: boolean
}

interface Pending extends ConfirmOptions {
  resolve: (ok: boolean) => void
}

export const confirmState = reactive<{ current: Pending | null }>({ current: null })

/** Promise-based replacement for window.confirm(). */
export function confirmAction(options: ConfirmOptions): Promise<boolean> {
  return new Promise((resolve) => {
    confirmState.current?.resolve(false)
    confirmState.current = { ...options, resolve }
  })
}

export function settleConfirm(ok: boolean): void {
  confirmState.current?.resolve(ok)
  confirmState.current = null
}
