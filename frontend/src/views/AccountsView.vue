<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Plus } from '@lucide/vue'
import AccountCard from '@/components/AccountCard.vue'
import AccountDialog from '@/components/AccountDialog.vue'
import PageHead from '@/components/PageHead.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { api, ApiError } from '@/lib/api'
import type { TabKey } from '@/lib/accountForm'
import { confirmAction } from '@/lib/confirm'
import { describe } from '@/lib/messages'
import { refresh, store } from '@/lib/store'
import { toast } from '@/lib/toast'
import type { Account } from '@/lib/types'

const route = useRoute()
const router = useRouter()

// The dialog follows the URL, so every editor state is linkable: ?new=1 or ?edit=<id>&tab=<tab>
const TABS: TabKey[] = ['basic', 'schedule', 'keywords', 'messages', 'alerts']
const editing = computed(() => (route.query.edit ? store.accounts.find((a) => a.id === route.query.edit) ?? null : null))
const open = computed(() => route.query.new === '1' || !!editing.value)
const tab = computed(() => TABS.find((t) => t === route.query.tab))

const edit = (id: string, to?: TabKey): void => void router.push({ query: { edit: id, ...(to ? { tab: to } : {}) } })
const close = (): void => void router.replace({ query: {} })

const summary = computed(() => {
  const a = store.accounts
  return `共 ${a.length} 个账号 · ${a.filter((x) => x.enabled).length} 个启用 · ${a.filter((x) => x.keyword_monitor_enabled).length} 个关键词监听 · ${a.filter((x) => x.message_monitor_enabled).length} 个私信通知 · ${a.filter((x) => x.offline_notify_enabled).length} 个掉线通知`
})

async function remove(account: Account): Promise<void> {
  const ok = await confirmAction({ title: `删除账号“${account.name}”？`, message: '同时会取消它排队中的任务。已有的执行记录会保留，但账号和 Cookie 无法恢复。', confirmText: '删除账号', danger: true })
  if (!ok) return
  try {
    await api.deleteAccount(account.id)
    toast.ok('账号已删除')
    await refresh()
  } catch (error) {
    toast.error(describe(error instanceof ApiError ? error.code : 'REQUEST_FAILED'))
  }
}
</script>

<template>
  <PageHead>
    <BaseButton variant="primary" @click="router.push({ query: { new: '1' } })"><template #icon><Plus :size="16" /></template>添加账号</BaseButton>
  </PageHead>
  <div class="summary">{{ summary }}</div>

  <div class="account-list">
    <AccountCard v-for="a in store.accounts" :key="a.id" :account="a" @edit="edit(a.id, $event)" @remove="remove(a)" />
    <div v-if="!store.accounts.length" class="panel empty">暂无签到账号，点击“添加账号”开始配置。</div>
  </div>

  <AccountDialog :open="open" :account="editing" :tab="tab" @close="close" />
</template>

<style scoped>
.account-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 12px; align-items: start; }
.account-list .empty { grid-column: 1 / -1; }
</style>
