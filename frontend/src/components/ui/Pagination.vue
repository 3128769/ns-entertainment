<script setup lang="ts">
import { computed } from 'vue'
import { ChevronLeft, ChevronRight } from '@lucide/vue'

const props = defineProps<{ page: number; pageSize: number; total: number; busy?: boolean }>()
defineEmits<{ change: [page: number] }>()
const pages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))
</script>

<template>
  <div class="pagination">
    <span>第 {{ page }} / {{ pages }} 页 · 每页 {{ pageSize }} 条</span>
    <div class="pages">
      <button type="button" aria-label="上一页" :disabled="page <= 1 || busy" @click="$emit('change', page - 1)"><ChevronLeft :size="16" /></button>
      <button type="button" aria-label="下一页" :disabled="page >= pages || busy" @click="$emit('change', page + 1)"><ChevronRight :size="16" /></button>
    </div>
  </div>
</template>
