<script setup lang="ts">
import { reactive } from 'vue'
import { Pencil, Plus, RefreshCw, Server, Trash2 } from '@lucide/vue'
import PageHead from '@/components/PageHead.vue'
import ProxyDialog from '@/components/ProxyDialog.vue'
import Badge from '@/components/ui/Badge.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { api, ApiError } from '@/lib/api'
import { confirmAction } from '@/lib/confirm'
import { describe } from '@/lib/messages'
import { actions, isPending, refresh, store } from '@/lib/store'
import { toast } from '@/lib/toast'
import { formatFull, formatTime } from '@/lib/time'
import type { Proxy } from '@/lib/types'

const dialog = reactive<{ open: boolean; proxy: Proxy | null }>({ open: false, proxy: null })
const open = (proxy: Proxy | null): void => void Object.assign(dialog, { open: true, proxy })

async function remove(proxy: Proxy): Promise<void> {
  if (proxy.assigned_count) {
    toast.error(`有 ${proxy.assigned_count} 个账号正在使用“${proxy.name}”，请先为它们更换代理`)
    return
  }
  if (!(await confirmAction({ title: `删除代理“${proxy.name}”？`, message: '删除后无法恢复。', confirmText: '删除代理', danger: true }))) return
  try {
    await api.deleteProxy(proxy.id)
    toast.ok('代理已删除')
    await refresh()
  } catch (error) {
    toast.error(describe(error instanceof ApiError ? error.code : 'REQUEST_FAILED'))
  }
}
</script>

<template>
  <PageHead><BaseButton variant="primary" @click="open(null)"><template #icon><Plus :size="16" /></template>添加代理</BaseButton></PageHead>

  <section class="panel">
    <div class="panel-head">
      <div><div class="panel-title">代理线路</div><div class="panel-desc">编辑时链接留空，可只修改名称和备注</div></div>
      <span class="panel-count">{{ store.proxies.length }} 条线路</span>
    </div>
    <div v-if="!store.proxies.length" class="empty">暂无代理，账号将使用直连。</div>
    <div v-else class="row-list">
      <div v-for="p in store.proxies" :key="p.id" class="row-item">
        <div class="row-main">
          <div class="row-title"><span class="glyph"><Server :size="18" /></span>{{ p.name }}</div>
          <div class="row-sub">{{ p.protocol }} · {{ p.host }}:{{ p.port }}<template v-if="p.remark"> · {{ p.remark }}</template> · {{ p.assigned_count ? `${p.assigned_count} 个账号使用` : '未被使用' }}</div>
        </div>
        <div class="row-state">
          <Badge :tone="p.last_test_success === null ? 'muted' : p.last_test_success ? 'ok' : 'bad'">{{ p.last_test_success === null ? '未测试' : p.last_test_success ? '连接正常' : '连接失败' }}</Badge>
          <span v-if="p.last_tested_at" :title="formatFull(p.last_tested_at)">{{ formatTime(p.last_tested_at) }}<template v-if="p.last_test_latency_ms != null"> · {{ p.last_test_latency_ms }}ms</template></span>
        </div>
        <div class="row-actions">
          <BaseButton variant="action" :loading="isPending(`proxy:${p.id}`)" @click="actions.testProxy(p)"><template #icon><RefreshCw :size="15" /></template>测试连接</BaseButton>
          <BaseButton variant="ghost" @click="open(p)"><template #icon><Pencil :size="15" /></template>编辑</BaseButton>
          <BaseButton variant="danger" icon-only :aria-label="`删除代理 ${p.name}`" :title="`删除代理 ${p.name}`" @click="remove(p)"><template #icon><Trash2 :size="15" /></template></BaseButton>
        </div>
      </div>
    </div>
  </section>

  <ProxyDialog :open="dialog.open" :proxy="dialog.proxy" @close="dialog.open = false" />
</template>
