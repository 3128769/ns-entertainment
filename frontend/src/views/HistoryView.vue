<script setup lang="ts">
import HistoryPanel from '@/components/HistoryPanel.vue'
import PageHead from '@/components/PageHead.vue'
</script>

<template>
  <PageHead />
  <HistoryPanel kind="checkin" title="签到执行记录" desc="自动和手动执行结果，按页加载" empty-text="暂无签到记录" />
</template>
