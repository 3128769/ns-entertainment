<script setup lang="ts">
defineProps<{ label: string; hint?: string; error?: string; for?: string; required?: boolean }>()
</script>

<template>
  <div class="field">
    <label :for="$props.for">{{ label }}<span v-if="required" class="req" aria-hidden="true"> *</span></label>
    <slot />
    <small v-if="error" class="error" role="alert">{{ error }}</small>
    <small v-else-if="hint">{{ hint }}</small>
  </div>
</template>
