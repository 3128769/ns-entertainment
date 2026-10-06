<script setup lang="ts">
import { Loader2 } from '@lucide/vue'

/**
 * primary / secondary: the page-level buttons (34px).
 * action / ghost / violet / danger: the in-row actions (36px, 12px text).
 */
withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'action' | 'ghost' | 'violet' | 'danger'
    size?: 'md' | 'sm'
    loading?: boolean
    disabled?: boolean
    type?: 'button' | 'submit'
    iconOnly?: boolean
  }>(),
  { variant: 'secondary', size: 'md', type: 'button' },
)
</script>

<template>
  <button class="b" :class="[variant, size, { icon: iconOnly }]" :type="type" :disabled="disabled || loading" :aria-busy="loading || undefined">
    <Loader2 v-if="loading" :size="15" class="spin" aria-hidden="true" />
    <slot v-else name="icon" />
    <span v-if="$slots.default"><slot /></span>
  </button>
</template>

<style scoped>
.b { display: inline-flex; align-items: center; justify-content: center; gap: 7px; height: 34px; padding: 0 12px; border: 1px solid transparent; border-radius: 8px; font-size: 13px; font-weight: 500; line-height: 1.45; white-space: nowrap; transition: background 0.12s, border-color 0.12s, color 0.12s, opacity 0.12s; }
.b:disabled { opacity: 0.5; }
.b.icon { width: 34px; padding: 0; }

.secondary { background: var(--panel); border-color: var(--line); color: var(--text); }
.secondary:hover:not(:disabled) { background: var(--panel2); }
.primary { background: var(--black); border-color: var(--black); color: var(--on-black); }
.primary:hover:not(:disabled) { opacity: 0.88; }

.action, .ghost, .violet, .danger { height: 36px; padding: 0 10px; gap: 6px; font-size: 12px; line-height: 12px; background: transparent; }
.action.icon, .ghost.icon, .violet.icon, .danger.icon { width: 36px; padding: 0; }
.sm.action, .sm.ghost, .sm.violet, .sm.danger { height: 30px; padding: 0 8px; }
.sm.icon { width: 30px; }
.action { background: var(--accent-soft); color: #171717; }
:root[data-theme='dark'] .action { color: var(--text); }
.action:hover:not(:disabled) { background: var(--line); }
.ghost { color: var(--sub); }
.ghost:hover:not(:disabled) { background: var(--accent-soft); color: var(--text); }
.violet { color: var(--violet); }
.violet:hover:not(:disabled) { background: color-mix(in srgb, var(--violet) 10%, transparent); }
.danger { color: var(--red); }
.danger:hover:not(:disabled) { background: color-mix(in srgb, var(--red) 9%, transparent); }
</style>
