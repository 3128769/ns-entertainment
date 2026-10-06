<script setup lang="ts">
import { Bell, Pencil, Play, Radar } from '@lucide/vue'
import Badge from './ui/Badge.vue'
import BaseButton from './ui/BaseButton.vue'
import { proxyName, scheduleLabel, taskHealth, type TaskKind } from '@/lib/account'
import { actions, isPending, store } from '@/lib/store'
import { formatFull, formatTime } from '@/lib/time'
import type { Tone } from '@/lib/messages'
import type { Account } from '@/lib/types'

defineProps<{ account: Account }>()
defineEmits<{ edit: [] }>()

const TASKS: { kind: TaskKind; label: string }[] = [
  { kind: 'checkin', label: '签到' },
  { kind: 'keyword', label: '关键词' },
  { kind: 'message', label: '私信' },
  { kind: 'cookie', label: 'Cookie' },
]
const TONE: Record<string, Tone> = { ok: 'ok', bad: 'bad', warn: 'bad', idle: 'muted', off: 'muted' }
</script>

<template>
  <div class="status-row">
    <div class="who">
      <div class="status-name">{{ account.name }}</div>
      <div class="status-sub">{{ proxyName(store.proxies, account.proxy_id) }} · {{ scheduleLabel(account) }}</div>
    </div>
    <div class="task-grid">
      <div v-for="task in TASKS" :key="task.kind">
        <span class="label">{{ task.label }}</span>
        <template v-for="health in [taskHealth(account, task.kind)]" :key="task.kind">
          <span v-if="health.state === 'off'" class="off">{{ health.label }}</span>
          <template v-else>
            <Badge :tone="TONE[health.state]">{{ health.label }}</Badge>
            <time v-if="health.at" class="when" :title="formatFull(health.at)">{{ formatTime(health.at) }}</time>
          </template>
        </template>
      </div>
    </div>
    <div class="row-actions">
      <BaseButton variant="action" :loading="isPending(`checkin:${account.id}`)" :disabled="!store.worker?.ready" :title="store.worker?.ready ? '立即签到' : '后台服务未运行'" @click="actions.checkin(account)"><template #icon><Play :size="15" /></template>签到</BaseButton>
      <BaseButton v-if="account.keyword_monitor_enabled" variant="violet" :loading="isPending(`keyword:${account.id}`)" :disabled="!store.worker?.ready" title="立即检查关键词" @click="actions.keywordCheck(account)"><template #icon><Radar :size="15" /></template>关键词</BaseButton>
      <BaseButton v-if="account.message_monitor_enabled" variant="violet" :loading="isPending(`message:${account.id}`)" :disabled="!store.worker?.ready" title="立即检查私信" @click="actions.messageCheck(account)"><template #icon><Bell :size="15" /></template>私信</BaseButton>
      <BaseButton variant="ghost" @click="$emit('edit')"><template #icon><Pencil :size="15" /></template>编辑</BaseButton>
    </div>
  </div>
</template>

<style scoped>
.status-row { display: grid; grid-template-columns: minmax(150px, 1fr) auto auto; align-items: center; gap: 12px 16px; padding: 14px 16px; background: var(--panel); border: 1px solid var(--line); border-radius: var(--r-lg); box-shadow: var(--shadow); }
.status-name { font-size: 14px; font-weight: 600; overflow-wrap: anywhere; }
.status-sub { margin-top: 3px; font-size: 12px; color: var(--sub); }
.task-grid { display: grid; grid-template-columns: repeat(4, 85px); gap: 8px; }
.task-grid > div { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; padding: 8px 10px; background: var(--panel2); border: 1px solid var(--line); border-radius: 10px; min-width: 0; }
.label { font-size: 11px; color: var(--muted); }
.off { font-size: 12px; color: var(--muted); }
.when { font-size: 13px; line-height: 1.35; font-variant-numeric: tabular-nums; }
.row-actions { display: flex; gap: 6px; justify-content: flex-end; flex-wrap: wrap; }
@media (max-width: 1180px) {
  .status-row { grid-template-columns: minmax(0, 1fr); }
  .task-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .row-actions { justify-content: flex-start; }
}
@media (max-width: 560px) { .task-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
