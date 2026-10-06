<script setup lang="ts">
import { computed } from 'vue'
import { store } from '@/lib/store'
import { relativeTime } from '@/lib/time'

const state = computed(() => {
  const worker = store.worker
  if (!worker) return { tone: 'muted', label: '检查中…', hint: '' }
  const queued = (worker.counts.queued ?? 0) + (worker.counts.retry_wait ?? 0)
  const running = worker.counts.running ?? 0
  if (!worker.ready) return { tone: 'bad', label: '后台服务离线', hint: '签到与监听已暂停' }
  const busy = running + queued
  return { tone: 'ok', label: '后台服务运行中', hint: busy ? `${running} 个执行中 · ${queued} 个排队` : `心跳 ${relativeTime(worker.heartbeat_at)}` }
})
</script>

<template>
  <div class="worker" :class="state.tone" :title="store.worker ? `并发 ${store.worker.concurrency ?? '-'} · v${store.worker.version}` : ''">
    <i class="dot" aria-hidden="true" />
    <div class="text">
      <strong>{{ state.label }}</strong>
      <span v-if="state.hint">{{ state.hint }}</span>
    </div>
  </div>
</template>

<style scoped>
.worker { display: flex; align-items: center; gap: 10px; padding: 9px 11px; border-radius: 10px; background: var(--surface-2); border: 1px solid var(--line); }
.dot { width: 8px; height: 8px; border-radius: 50%; flex: none; background: var(--text-3); }
.ok .dot { background: var(--ok); box-shadow: 0 0 0 3px color-mix(in srgb, var(--ok) 22%, transparent); }
.bad { background: var(--bad-soft); border-color: var(--bad-line); }
.bad .dot { background: var(--bad); box-shadow: 0 0 0 3px color-mix(in srgb, var(--bad) 22%, transparent); }
.text { display: grid; min-width: 0; line-height: 1.3; }
strong { font-size: 12.5px; font-weight: 600; }
.bad strong { color: var(--bad); }
span { font-size: 11.5px; color: var(--text-3); }
</style>
