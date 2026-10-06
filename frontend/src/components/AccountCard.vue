<script setup lang="ts">
import { Bell, BellRing, CalendarClock, Clock, Cookie, Dices, Network, Pencil, Play, Radar, Trash2 } from '@lucide/vue'
import Badge from './ui/Badge.vue'
import BaseButton from './ui/BaseButton.vue'
import Chip from './ui/Chip.vue'
import { cookieState, proxyName, scheduleLabel } from '@/lib/account'
import { describe, statusInfo } from '@/lib/messages'
import { actions, isPending, store } from '@/lib/store'
import { formatTime } from '@/lib/time'
import type { Account } from '@/lib/types'
import type { TabKey } from '@/lib/accountForm'

const props = defineProps<{ account: Account }>()
const emit = defineEmits<{ edit: [tab?: TabKey]; remove: [] }>()

const result = () => statusInfo(props.account.last_status)
const busy = () => isPending(`checkin:${props.account.id}`) || isPending(`keyword:${props.account.id}`) || isPending(`message:${props.account.id}`)
</script>

<template>
  <article class="account-row">
    <div class="account-head">
      <div class="account-id">
        <div class="account-name" :title="account.name">{{ account.name }}</div>
        <div class="account-sub"><Cookie :size="14" />{{ cookieState(account).label }}</div>
      </div>
      <div class="account-badges">
        <Badge :tone="cookieState(account).tone">{{ cookieState(account).label }}</Badge>
        <Badge :tone="account.enabled ? 'ok' : 'muted'">{{ account.enabled ? '已启用' : '已暂停' }}</Badge>
      </div>
    </div>

    <div class="chips">
      <Chip tone="warn"><template #icon><Dices :size="14" /></template>{{ account.random_checkin ? '随机手气' : '固定手气' }}</Chip>
      <Chip tone="blue"><template #icon><CalendarClock :size="14" /></template>{{ scheduleLabel(account) }}</Chip>
      <Chip :tone="account.proxy_id ? 'ok' : 'muted'"><template #icon><Network :size="14" /></template>{{ proxyName(store.proxies, account.proxy_id) }}</Chip>
      <Chip as="button" :tone="account.keyword_monitor_enabled ? 'violet' : 'muted'" @click="emit('edit', 'keywords')"><template #icon><component :is="account.keyword_monitor_enabled ? BellRing : Radar" :size="14" /></template>{{ account.keyword_monitor_enabled ? `${account.keywords.length} 个关键词` : '监听未启用' }}</Chip>
      <Chip as="button" :tone="account.message_monitor_enabled ? 'violet' : 'muted'" @click="emit('edit', 'messages')"><template #icon><Bell :size="14" /></template>{{ account.message_monitor_enabled ? '私信通知' : '私信未启用' }}</Chip>
      <Chip v-if="account.offline_notify_enabled" as="button" tone="ok" @click="emit('edit', 'alerts')"><template #icon><Cookie :size="14" /></template>掉线通知</Chip>
    </div>

    <div class="result-line">
      <Badge :tone="result().tone">{{ result().label }}</Badge>
      <span class="result-msg" :title="describe(account.last_message)">{{ describe(account.last_message) }}</span>
    </div>

    <div v-if="account.keyword_monitor_enabled" class="monitor-detail">
      <BellRing :size="17" class="vi" />
      <div>
        <div class="monitor-heading">
          <Badge :tone="statusInfo(account.last_monitor_status).tone">{{ statusInfo(account.last_monitor_status).label }}</Badge>
          <span>{{ account.last_monitor_at ? `检查于 ${formatTime(account.last_monitor_at)}` : '等待首次检查' }}</span>
        </div>
        <div class="monitor-keywords">{{ account.keywords.join(' · ') || '未配置关键词' }}</div>
        <p class="monitor-message">{{ describe(account.last_monitor_message ?? '等待监听检查') }}</p>
      </div>
    </div>
    <div v-else class="monitor-detail is-off">
      <Radar :size="17" />
      <div>
        <div class="monitor-heading"><span>关键词监听未启用</span></div>
        <p class="monitor-message">点击上方“监听未启用”可开启关键词与通知。</p>
      </div>
    </div>

    <div v-if="account.message_monitor_enabled" class="monitor-detail">
      <Bell :size="17" class="vi" />
      <div>
        <div class="monitor-heading">
          <Badge :tone="statusInfo(account.last_message_monitor_status).tone">{{ statusInfo(account.last_message_monitor_status).label }}</Badge>
          <span>{{ account.last_message_monitor_at ? `检查于 ${formatTime(account.last_message_monitor_at)}` : '等待首次检查' }}</span>
        </div>
        <p class="monitor-message">{{ describe(account.last_message_monitor_message ?? '等待私信检查') }}</p>
      </div>
    </div>

    <div class="account-foot">
      <span class="account-time"><Clock :size="14" />{{ account.last_run_at ? `上次签到 ${formatTime(account.last_run_at)}` : '尚未执行签到' }}</span>
      <div class="row-actions">
        <BaseButton variant="action" :loading="isPending(`checkin:${account.id}`)" :disabled="!store.worker?.ready" title="立即签到" @click="actions.checkin(account)"><template #icon><Play :size="15" /></template>签到</BaseButton>
        <BaseButton v-if="account.keyword_monitor_enabled" variant="violet" :loading="isPending(`keyword:${account.id}`)" :disabled="!store.worker?.ready" title="立即检查关键词" @click="actions.keywordCheck(account)"><template #icon><BellRing :size="15" /></template>检查</BaseButton>
        <BaseButton variant="ghost" :disabled="busy()" @click="emit('edit')"><template #icon><Pencil :size="15" /></template>编辑</BaseButton>
        <BaseButton variant="danger" icon-only class="del" :disabled="busy()" :aria-label="`删除账号 ${account.name}`" :title="`删除账号 ${account.name}`" @click="emit('remove')"><template #icon><Trash2 :size="15" /></template></BaseButton>
      </div>
    </div>
  </article>
</template>

<style scoped>
.account-row { display: flex; flex-direction: column; min-width: 0; padding: 16px; background: var(--panel); border: 1px solid var(--line); border-radius: var(--r-lg); box-shadow: var(--shadow); }
.account-head { display: flex; justify-content: space-between; gap: 12px; }
.account-id { min-width: 0; }
.account-name { font-size: 15px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.account-sub { display: flex; align-items: center; gap: 5px; margin-top: 4px; font-size: 11px; color: var(--sub); }
.account-badges { display: flex; align-items: flex-start; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 14px; }
.result-line { display: flex; align-items: flex-start; gap: 8px; margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--line); }
.result-msg { font-size: 12px; line-height: 18px; color: var(--sub); overflow-wrap: anywhere; }
.monitor-detail { display: flex; gap: 6px; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--line); font-size: 11px; color: var(--sub); }
.monitor-detail > svg { margin-top: 2px; }
.monitor-detail > svg.vi { color: var(--violet); }
.monitor-detail.is-off { opacity: 0.78; }
.monitor-heading { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
.monitor-keywords { margin-top: 7px; line-height: 18px; overflow-wrap: anywhere; }
.monitor-message { line-height: 18px; margin-top: 3px; overflow-wrap: anywhere; }
.account-foot { margin-top: auto; padding-top: 20px; }
.account-time { display: flex; align-items: center; gap: 5px; margin-bottom: 10px; font-size: 11px; color: var(--muted); }
.row-actions { display: flex; align-items: center; gap: 8px; }
.del { margin-left: auto; }
</style>
