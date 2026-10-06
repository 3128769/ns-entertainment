<script setup lang="ts">
defineProps<{ title: string; hint?: string }>()
</script>

<template>
  <div class="empty">
    <p class="t">{{ title }}</p>
    <p v-if="hint" class="h">{{ hint }}</p>
    <div v-if="$slots.default" class="a"><slot /></div>
  </div>
</template>

<style scoped>
.t { color: var(--text); font-weight: 500; }
.h { margin-top: 4px; font-size: 12px; color: var(--sub); }
.a { margin-top: 14px; display: flex; justify-content: center; }
</style>
