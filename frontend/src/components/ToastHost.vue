<script setup lang="ts">
import { dismiss, toasts } from '@/lib/toast'
</script>

<template>
  <Teleport to="body">
    <div class="host" aria-live="polite">
      <TransitionGroup name="toast">
        <button v-for="item in toasts" :key="item.id" type="button" class="toast" :class="item.tone" :role="item.tone === 'bad' ? 'alert' : 'status'" @click="dismiss(item.id)">{{ item.text }}</button>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.host { position: fixed; z-index: 80; right: 15px; bottom: 15px; display: grid; gap: 7px; max-width: calc(100% - 30px); width: max-content; justify-items: end; pointer-events: none; }
.toast { pointer-events: auto; max-width: 420px; padding: 9px 12px; border: 0; border-radius: 6px; background: #111827; color: #fff; font-size: 12px; line-height: 1.5; text-align: left; box-shadow: 0 8px 25px rgb(17 24 39 / 0.22); overflow-wrap: anywhere; }
.toast.bad { background: #9f1239; }
.toast-enter-active, .toast-leave-active { transition: transform 0.2s, opacity 0.2s; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(8px); }
</style>
