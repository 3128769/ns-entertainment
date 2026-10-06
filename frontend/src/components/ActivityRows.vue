<script setup lang="ts">
import { computed } from 'vue'
import Badge from './ui/Badge.vue'
import { describe, SOURCE_LABEL, statusInfo } from '@/lib/messages'
import { formatFull, formatTime } from '@/lib/time'
import type { HistoryKind, RunRecord } from '@/lib/types'

const props = defineProps<{ items: RunRecord[]; kind: HistoryKind; empty?: string; limit?: number }>()

function detail(item: RunRecord): string {
  const bits: string[] = []
  if (props.kind === 'checkin' && item.gained != null) bits.push(`收益 ${item.gained} 个鸡腿`)
  if (props.kind === 'monitor') bits.push(`检查 ${item.checked ?? 0}`, `新原帖 ${item.new_posts ?? 0}`, `命中 ${item.matched ?? 0}`)
  if (props.kind === 'message') bits.push(`检查 ${item.checked ?? 0}`, `新私信 ${item.new_messages ?? 0}`)
  bits.push(SOURCE_LABEL[item.source] ?? item.source)
  return bits.join(' · ')
}

const rows = computed(() => props.items.slice(0, props.limit ?? props.items.length).map((item) => ({ item, status: statusInfo(item.status), text: describe(item.message), detail: detail(item) })))
</script>

<template>
  <div v-if="!rows.length" class="empty">{{ empty ?? '暂无符合条件的记录' }}</div>
  <div v-else>
    <div v-for="({ item, status, text, detail: meta }, index) in rows" :key="`${item.ran_at}-${item.account_id}-${index}`" class="activity-row">
      <div class="activity-meta">
        <span class="activity-name">{{ item.account_name || '未知账号' }}</span>
        <time class="activity-time" :title="formatFull(item.ran_at)" :datetime="item.ran_at">{{ formatTime(item.ran_at) }}</time>
      </div>
      <div class="activity-copy">
        <div class="activity-main">{{ text }}</div>
        <div class="activity-detail">{{ meta }}</div>
      </div>
      <div class="activity-status"><Badge :tone="status.tone">{{ status.label }}</Badge></div>
    </div>
  </div>
</template>
