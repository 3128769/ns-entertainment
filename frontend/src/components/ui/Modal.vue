<script setup lang="ts">
import { ref, toRef } from 'vue'
import { X } from '@lucide/vue'
import { useOverlay } from './useOverlay'

const props = defineProps<{ open: boolean; title: string; subtitle?: string; width?: number }>()
const emit = defineEmits<{ close: [] }>()
const panel = ref<HTMLElement | null>(null)
useOverlay(toRef(props, 'open'), panel, () => emit('close'))
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" class="back" @mousedown.self="emit('close')">
        <section ref="panel" class="modal" role="dialog" aria-modal="true" :aria-label="title" :style="{ '--w': `${width ?? 630}px` }">
          <header class="head">
            <div class="grow">
              <h2>{{ title }}</h2>
              <p v-if="subtitle">{{ subtitle }}</p>
            </div>
            <slot name="head-extra" />
            <button type="button" class="close" aria-label="关闭" @click="emit('close')"><X :size="18" /></button>
          </header>
          <div v-if="$slots.tabs"><slot name="tabs" /></div>
          <div class="body"><slot /></div>
          <footer v-if="$slots.footer" class="foot"><slot name="footer" /></footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.back { position: fixed; inset: 0; z-index: 60; display: grid; place-items: center; padding: 12px; background: var(--scrim); }
.modal { display: flex; flex-direction: column; width: min(var(--w), 100%); max-height: calc(100dvh - 24px); background: var(--panel); border: 1px solid var(--line); border-radius: 16px; box-shadow: var(--modal-shadow); overflow: hidden; }
.head { display: flex; align-items: flex-start; gap: 10px; padding: 16px 18px; }
.head h2 { font-size: 16px; font-weight: 600; line-height: 23px; }
.head p { margin-top: 4px; font-size: 11px; color: var(--sub); }
.grow { flex: 1; min-width: 0; }
.close { display: grid; place-items: center; width: 36px; height: 36px; margin: -6px -8px 0 0; padding: 0; border: 0; border-radius: 8px; background: transparent; color: var(--sub); }
.close:hover { background: var(--panel2); color: var(--text); }
.body { padding: 18px; overflow-y: auto; overscroll-behavior: contain; }
.foot { display: flex; justify-content: flex-end; align-items: center; gap: 7px; padding: 12px 18px; border-top: 1px solid var(--line); background: var(--panel); }
.modal-enter-active, .modal-leave-active { transition: opacity 0.15s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
</style>
