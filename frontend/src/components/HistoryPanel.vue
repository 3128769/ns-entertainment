<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ActivityRows from './ActivityRows.vue'
import { api, ApiError } from '@/lib/api'
import { describe, statusInfo } from '@/lib/messages'
import { store } from '@/lib/store'
import type { HistoryKind, RunRecord } from '@/lib/types'
import Pagination from './ui/Pagination.vue'

const props = defineProps<{ kind: HistoryKind; title: string; desc: string; emptyText: string }>()

const PAGE_SIZE = 20
const STATUSES: Record<HistoryKind, string[]> = {
  checkin: ['success', 'already', 'failed', 'uncertain', 'nodeseek_auth_expired', 'nodeseek_cloudflare_blocked'],
  monitor: ['notified', 'notify_failed', 'baseline', 'failed'],
  message: ['notified', 'notify_failed', 'baseline', 'failed'],
}

const account = ref('')
const status = ref('')
const page = ref(1)
const items = ref<RunRecord[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref('')

const statusOptions = computed(() => STATUSES[props.kind].map((value) => ({ value, label: statusInfo(value).label })))

let token = 0
async function load(): Promise<void> {
  const mine = ++token
  loading.value = true
  try {
    const result = await api.history(props.kind, { limit: PAGE_SIZE, offset: (page.value - 1) * PAGE_SIZE, account_id: account.value || undefined, status: status.value || undefined })
    if (mine !== token) return // superseded by a newer request
    const last = Math.max(1, Math.ceil(result.total / PAGE_SIZE))
    if (page.value > last) {
      page.value = last
      return void load()
    }
    items.value = result.items
    total.value = result.total
    error.value = ''
  } catch (e) {
    if (mine === token) error.value = describe(e instanceof ApiError ? e.code : 'REQUEST_FAILED')
  } finally {
    if (mine === token) loading.value = false
  }
}

watch([account, status], () => {
  page.value = 1
  void load()
}, { immediate: true })
watch(() => store.updatedAt, () => void load()) // follow the background refresh
</script>

<template>
  <section class="panel">
    <div class="panel-head">
      <div><div class="panel-title">{{ title }}</div><div class="panel-desc">{{ desc }}</div></div>
    </div>
    <div class="record-tools">
      <div class="record-filters">
        <label>账号
          <select v-model="account" aria-label="筛选账号">
            <option value="">全部账号</option>
            <option v-for="a in store.accounts" :key="a.id" :value="a.id">{{ a.name }}</option>
          </select>
        </label>
        <label>状态
          <select v-model="status" aria-label="筛选状态">
            <option value="">全部状态</option>
            <option v-for="s in statusOptions" :key="s.value" :value="s.value">{{ s.label }}</option>
          </select>
        </label>
      </div>
      <span class="record-count">{{ total }} 条记录 · 当前显示 {{ items.length }} 条</span>
    </div>
    <div v-if="error" class="empty" role="alert">{{ error }}</div>
    <ActivityRows v-else :items="items" :kind="kind" :empty="account || status ? '暂无符合条件的记录' : emptyText" />
    <Pagination :page="page" :page-size="PAGE_SIZE" :total="total" :busy="loading" @change="((page = $event), load())" />
  </section>
</template>
