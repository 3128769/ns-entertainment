import { ref, watchEffect } from 'vue'

export type Theme = 'light' | 'dark'

const KEY = 'ns_theme_v4' // same key and values as the previous interface, so the choice carries over

function initial(): Theme {
  try {
    const saved = localStorage.getItem(KEY)
    if (saved === 'light' || saved === 'dark') return saved
  } catch {
    /* storage unavailable */
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export const theme = ref<Theme>(initial())

export function toggleTheme(): void {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
  try {
    localStorage.setItem(KEY, theme.value)
  } catch {
    /* ignore */
  }
}

export function startTheme(): void {
  watchEffect(() => {
    document.documentElement.dataset.theme = theme.value
  })
}
