<script setup lang="ts">
defineProps<{ modelValue: boolean; label: string; disabled?: boolean }>()
defineEmits<{ 'update:modelValue': [value: boolean] }>()
</script>

<template>
  <button type="button" role="switch" class="switch" :class="{ on: modelValue }" :aria-checked="modelValue" :aria-label="label" :disabled="disabled" @click="$emit('update:modelValue', !modelValue)">
    <span class="thumb" />
  </button>
</template>

<style scoped>
.switch { position: relative; flex: none; width: 34px; height: 20px; padding: 0; border: 0; border-radius: 999px; background: var(--strong); transition: background 0.15s; }
.switch.on { background: var(--black); }
.switch:disabled { opacity: 0.5; cursor: not-allowed; }
.thumb { position: absolute; top: 2px; left: 2px; width: 16px; height: 16px; border-radius: 50%; background: #fff; box-shadow: 0 1px 2px rgb(0 0 0 / 0.3); transition: transform 0.15s; }
:root[data-theme='dark'] .on .thumb { background: #18181b; }
.on .thumb { transform: translateX(14px); }
</style>
