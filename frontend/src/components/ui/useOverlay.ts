import { nextTick, onBeforeUnmount, watch, type Ref } from 'vue'

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
let locks = 0

/** Shared behaviour of drawers and dialogs: scroll lock, Esc, focus in/out, Tab containment. */
export function useOverlay(open: Ref<boolean>, panel: Ref<HTMLElement | null>, close: () => void): void {
  let previous: Element | null = null

  const onKey = (event: KeyboardEvent): void => {
    if (event.key === 'Escape') {
      event.stopPropagation()
      close()
      return
    }
    if (event.key !== 'Tab' || !panel.value) return
    const nodes = [...panel.value.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => el.offsetParent !== null)
    if (!nodes.length) return
    const first = nodes[0]!
    const last = nodes[nodes.length - 1]!
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  const release = (): void => {
    document.removeEventListener('keydown', onKey, true)
    locks = Math.max(0, locks - 1)
    if (!locks) document.documentElement.style.overflow = ''
    if (previous instanceof HTMLElement) previous.focus()
    previous = null
  }

  watch(open, async (isOpen, wasOpen) => {
    if (isOpen) {
      previous = document.activeElement
      locks += 1
      document.documentElement.style.overflow = 'hidden'
      document.addEventListener('keydown', onKey, true)
      await nextTick()
      const target = panel.value?.querySelector<HTMLElement>('[autofocus], input, textarea, select') ?? panel.value?.querySelector<HTMLElement>(FOCUSABLE)
      target?.focus()
    } else if (wasOpen) {
      release()
    }
  }, { immediate: true })

  onBeforeUnmount(() => {
    if (open.value) release()
  })
}
