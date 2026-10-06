<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Bell, Pencil, Radar } from '@lucide/vue'
import HistoryPanel from '@/components/HistoryPanel.vue'
import PageHead from '@/components/PageHead.vue'
import Badge from '@/components/ui/Badge.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import Switch from '@/components/ui/Switch.vue'
import { api, ApiError } from '@/lib/api'
import { botName } from '@/lib/account'
import { describe, statusInfo } from '@/lib/messages'
import { actions, isPending, refresh, store } from '@/lib/store'
import { toast } from '@/lib/toast'
import { formatFull, formatTime } from '@/lib/time'
import type { Account } from '@/lib/types'

const props = defineProps<{ kind: 'keywords' | 'messages' }>()
const router = useRouter()

const isKeywords = computed(() => props.kind === 'keywords')
const flag = computed<'keyword_monitor_enabled' | 'message_monitor_enabled'>(() => (isKeywords.value ? 'keyword_monitor_enabled' : 'message_monitor_enabled'))
const tab = computed(() => (isKeywords.value ? 'keywords' : 'messages'))
const enabledCount = computed(() => store.accounts.filter((a) => a[flag.value]).length)

function state(a: Account): { label: string; tone: ReturnType<typeof statusInfo>['tone']; at: string | null; error: string } {
  const status = isKeywords.value ? a.last_monitor_status : a.last_message_monitor_status
  const at = isKeywords.value ? a.last_monitor_at : a.last_message_monitor_at
  const message = isKeywords.value ? a.last_monitor_message : a.last_message_monitor_message
  const info = statusInfo(status)
  return { label: status ? info.label : '等待检查', tone: status ? info.tone : 'muted', at, error: ['failed', 'notify_failed'].includes(status ?? '') ? describe(message) : '' }
}

async function toggle(a: Account, on: boolean): Promise<void> {
  try {
    await api.updateAccount(a.id, { [flag.value]: on })
    await refresh()
  } catch (error) {
    // Switching a rule on needs a bot and receiver: send the user to the form that asks for them.
    toast.error(describe(error instanceof ApiError ? error.code : 'REQUEST_FAILED'))
    if (on) void router.push({ path: '/accounts', query: { edit: a.id, tab: tab.value } })
  }
}

const check = (a: Account) => (isKeywords.value ? actions.keywordCheck(a) : actions.messageCheck(a))
const busy = (a: Account) => isPending(`${isKeywords.value ? 'keyword' : 'message'}:${a.id}`)
</script>

<template>
  <PageHead />

  <section class="panel">
    <div class="panel-head">
      <div>
        <div class="panel-title">{{ isKeywords ? '关键词规则' : '私信规则' }}</div>
        <div class="panel-desc">{{ isKeywords ? '约每 15–20 秒检查 RSS 新帖。签到和私信在各自的页面设置' : '约每分钟检查新私信。关键词和签到在各自的页面设置' }}</div>
      </div>
      <span class="panel-count">{{ enabledCount }} 个已启用</span>
    </div>
    <div v-if="!store.accounts.length" class="empty">暂无签到账号。请先在签到账号页添加。</div>
    <div v-for="a in store.accounts" :key="a.id" class="route">
      <div class="route-main">
        <div class="route-title"><component :is="isKeywords ? Radar : Bell" :size="16" />{{ a.name }}</div>
        <div class="route-sub">
          <template v-if="!a[flag]">未启用</template>
          <template v-else-if="isKeywords">{{ a.keywords.join(' · ') || '未填写关键词' }}</template>
          <template v-else>{{ botName(store.bots, a.message_bot_id) }} · Chat {{ a.message_chat_id || '--' }}</template>
          <template v-if="!a.enabled && a[flag]"> · 账号已暂停，监听不会运行</template>
        </div>
      </div>
      <div class="route-state">
        <Badge :tone="a[flag] ? state(a).tone : 'muted'">{{ a[flag] ? state(a).label : '未启用' }}</Badge>
        <div :title="formatFull(state(a).at)">{{ state(a).at ? `上次检查 ${formatTime(state(a).at)}` : '尚未检查' }}</div>
        <div v-if="a[flag] && state(a).error" class="status-error">{{ state(a).error }}</div>
      </div>
      <div class="route-actions">
        <Switch :model-value="a[flag]" :label="`${a.name} ${isKeywords ? '关键词监听' : '私信通知'}`" @update:model-value="toggle(a, $event)" />
        <BaseButton v-if="a[flag]" variant="ghost" :loading="busy(a)" :disabled="!store.worker?.ready" @click="check(a)"><template #icon><component :is="isKeywords ? Radar : Bell" :size="15" /></template>立即检查</BaseButton>
        <BaseButton variant="ghost" @click="router.push({ path: '/accounts', query: { edit: a.id, tab } })"><template #icon><Pencil :size="15" /></template>{{ isKeywords ? '设置关键词' : '设置私信' }}</BaseButton>
      </div>
    </div>
  </section>

  <HistoryPanel v-if="isKeywords" kind="monitor" title="命中记录" desc="命中、通知与失败记录，按页加载" empty-text="暂无命中记录" />
  <HistoryPanel v-else kind="message" title="通知记录" desc="通知、基线与失败记录，按页加载" empty-text="暂无通知记录" />
</template>

<style scoped>
.route { display: flex; align-items: center; gap: 14px; padding: 16px; border-bottom: 1px solid var(--line); }
.route:last-child { border-bottom: 0; }
.route-main { flex: 1; min-width: 0; }
.route-title { display: flex; align-items: center; gap: 7px; font-size: 13px; font-weight: 500; min-width: 0; overflow-wrap: anywhere; }
.route-title svg { color: var(--icon); }
.route-sub { margin-top: 5px; font-size: 12px; line-height: 19px; color: var(--sub); overflow-wrap: anywhere; }
.route-state { display: grid; justify-items: end; gap: 5px; min-width: 120px; text-align: right; font-size: 11px; color: var(--muted); }
.status-error { max-width: 260px; color: var(--red); overflow-wrap: anywhere; }
.route-actions { display: flex; align-items: center; gap: 6px; flex: none; }
@media (max-width: 1100px) {
  .route { flex-wrap: wrap; }
  .route-state { margin-left: auto; }
  .route-actions { flex-basis: 100%; justify-content: flex-end; }
}
</style>
