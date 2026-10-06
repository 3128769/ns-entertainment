import { reactive } from 'vue'

const KEY = 'ns_token' // same key as the previous UI, so existing sessions survive the upgrade

function read(): string {
  try {
    return localStorage.getItem(KEY) ?? ''
  } catch {
    return ''
  }
}

export const auth = reactive({ token: read() })

export function setToken(token: string): void {
  auth.token = token
  try {
    localStorage.setItem(KEY, token)
  } catch {
    /* storage unavailable: the session just won't survive a reload */
  }
}

export function clearToken(): void {
  auth.token = ''
  try {
    localStorage.removeItem(KEY)
  } catch {
    /* ignore */
  }
}
