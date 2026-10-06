<script setup lang="ts" generic="T extends string">
defineProps<{ modelValue: T; items: { value: T; label: string; alert?: boolean }[]; label?: string }>()
defineEmits<{ 'update:modelValue': [value: T] }>()
</script>

<template>
  <div class="tabs" role="tablist" :aria-label="label">
    <button v-for="item in items" :key="item.value" type="button" role="tab" class="tab" :class="{ active: item.value === modelValue }" :aria-selected="item.value === modelValue" @click="$emit('update:modelValue', item.value)">
      {{ item.label }}<i v-if="item.alert" class="alert" aria-label="有问题" />
    </button>
  </div>
</template>

<style scoped>
.tabs { display: flex; gap: 2px; overflow-x: auto; border-bottom: 1px solid var(--line); padding: 0 12px; scrollbar-width: none; }
.tabs::-webkit-scrollbar { display: none; }
.tab { position: relative; display: inline-flex; align-items: center; gap: 6px; height: 38px; padding: 0 10px; border: 0; background: transparent; color: var(--sub); font-size: 13px; font-weight: 500; white-space: nowrap; }
.tab:hover { color: var(--text); }
.tab.active { color: var(--text); }
.tab.active::after { content: ''; position: absolute; left: 8px; right: 8px; bottom: -1px; height: 2px; border-radius: 2px; background: var(--black); }
.alert { width: 6px; height: 6px; border-radius: 50%; background: var(--red); }
</style>
