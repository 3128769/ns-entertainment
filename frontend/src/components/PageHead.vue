<script setup lang="ts">
import { RefreshCw } from '@lucide/vue'
import { useRoute } from 'vue-router'
import BaseButton from './ui/BaseButton.vue'
import { refresh, store } from '@/lib/store'
import { formatTime } from '@/lib/time'

const route = useRoute()
</script>

<template>
  <div class="page-head">
    <div>
      <h1>{{ route.meta.title }}</h1>
      <p>{{ route.meta.desc }}</p>
      <p class="sync-note" role="status">{{ store.loading ? '正在刷新…' : store.updatedAt ? `数据更新于 ${formatTime(new Date(store.updatedAt).toISOString())}` : '数据尚未加载' }}</p>
    </div>
    <div class="actions">
      <BaseButton :loading="store.loading" @click="refresh"><template #icon><RefreshCw :size="16" /></template>刷新</BaseButton>
      <slot />
    </div>
  </div>
</template>
