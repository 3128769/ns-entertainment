<script setup lang="ts">
import { reactive, ref } from 'vue'
import { Bot, Pencil, Plus, RefreshCw, Trash2 } from '@lucide/vue'
import BotDialog from '@/components/BotDialog.vue'
import PageHead from '@/components/PageHead.vue'
import Badge from '@/components/ui/Badge.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { api, ApiError } from '@/lib/api'
import { botUsage } from '@/lib/account'
import { confirmAction } from '@/lib/confirm'
import { describe } from '@/lib/messages'
import { isPending, refresh, store } from '@/lib/store'
import { toast } from '@/lib/toast'
import type { Bot as BotRecord } from '@/lib/types'

const dialog = reactive<{ open: boolean; bot: BotRecord | null }>({ open: false, bot: null })
const open = (bot: BotRecord | null): void => void Object.assign(dialog, { open: true, bot })
/** Result of the last "check connection" per bot, kept for this visit only. */
const checks = ref<Record<string, { ok: boolean; text: string }>>({})

async function check(bot: BotRecord): Promise<void> {
  const key = `bot:${bot.id}`
  if (isPending(key)) return
  store.pending[key] = true
  try {
    const result = await api.testBot(bot.id)
    checks.value[bot.id] = { ok: result.success, text: describe(result.message) }
    if (!result.success) toast.error(describe(result.message))
  } catch (error) {
    checks.value[bot.id] = { ok: false, text: describe(error instanceof ApiError ? error.code : 'REQUEST_FAILED') }
  } finally {
    delete store.pending[key]
  }
}

async function remove(bot: BotRecord): Promise<void> {
  const used = botUsage(store.accounts, bot.id)
  const ok = await confirmAction({
    title: `删除通知 Bot“${bot.name}”？`,
    message: used ? `有 ${used} 项监听或告警正在使用它，删除后这些通知会发送失败，请先在账号设置里改用其他 Bot。` : '删除后无法恢复，Token 也会一并清除。',
    confirmText: '删除 Bot',
    danger: true,
  })
  if (!ok) return
  try {
    await api.deleteBot(bot.id)
    toast.ok('通知 Bot 已删除')
    await refresh()
  } catch (error) {
    toast.error(describe(error instanceof ApiError ? error.code : 'REQUEST_FAILED'))
  }
}
</script>

<template>
  <PageHead><BaseButton variant="primary" @click="open(null)"><template #icon><Plus :size="16" /></template>添加 Bot</BaseButton></PageHead>

  <section class="panel">
    <div class="panel-head">
      <div><div class="panel-title">Telegram 通知 Bot</div><div class="panel-desc">检查连接校验 Token 和默认接收人，不发送消息；实际通知接收人以各账号设置为准</div></div>
      <span class="panel-count">{{ store.bots.length }} 个 Bot</span>
    </div>
    <div v-if="!store.bots.length" class="empty">暂无通知 Bot，添加后可在账号监听设置中选择。</div>
    <div v-else class="row-list">
      <div v-for="b in store.bots" :key="b.id" class="row-item">
        <div class="row-main">
          <div class="row-title"><span class="glyph"><Bot :size="18" /></span>{{ b.name }}</div>
          <div class="row-sub"><template v-if="b.username">@{{ b.username }} · </template>Chat ID {{ b.chat_id || '未设置' }} · {{ botUsage(store.accounts, b.id) ? `${botUsage(store.accounts, b.id)} 项在用` : '未被使用' }}</div>
        </div>
        <div class="row-state">
          <Badge :tone="checks[b.id] ? (checks[b.id]!.ok ? 'ok' : 'bad') : 'muted'">{{ checks[b.id] ? (checks[b.id]!.ok ? '校验通过' : '校验失败') : b.enabled ? '已启用 · 未校验' : '已停用' }}</Badge>
          <span v-if="checks[b.id]" role="status">{{ checks[b.id]!.text }}</span>
        </div>
        <div class="row-actions">
          <BaseButton variant="action" :loading="isPending(`bot:${b.id}`)" @click="check(b)"><template #icon><RefreshCw :size="15" /></template>检查连接</BaseButton>
          <BaseButton variant="ghost" @click="open(b)"><template #icon><Pencil :size="15" /></template>编辑</BaseButton>
          <BaseButton variant="danger" icon-only :aria-label="`删除通知 Bot ${b.name}`" :title="`删除通知 Bot ${b.name}`" @click="remove(b)"><template #icon><Trash2 :size="15" /></template></BaseButton>
        </div>
      </div>
    </div>
  </section>

  <BotDialog :open="dialog.open" :bot="dialog.bot" @close="dialog.open = false" />
</template>
