<script setup lang="ts" generic="T extends string | number | boolean">
defineProps<{ modelValue: T; options: { value: T; label: string }[]; label?: string }>()
defineEmits<{ 'update:modelValue': [value: T] }>()
</script>

<template>
  <div class="seg" role="radiogroup" :aria-label="label">
    <button v-for="option in options" :key="String(option.value)" type="button" role="radio" class="opt" :class="{ active: option.value === modelValue }" :aria-checked="option.value === modelValue" @click="$emit('update:modelValue', option.value)">{{ option.label }}</button>
  </div>
</template>

<style scoped>
.seg { display: inline-flex; padding: 3px; gap: 2px; background: var(--panel2); border: 1px solid var(--line); border-radius: 9px; }
.opt { height: 28px; padding: 0 12px; border: 1px solid transparent; border-radius: 6px; background: transparent; color: var(--sub); font-size: 12px; font-weight: 500; white-space: nowrap; }
.opt:hover:not(.active) { color: var(--text); }
.opt.active { background: var(--panel); border-color: var(--line); color: var(--text); }
</style>
