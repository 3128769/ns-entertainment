<script setup lang="ts">
import type { Component } from 'vue'

defineProps<{ label: string; value: string | number; hint: string; icon: Component; to?: string; bad?: boolean }>()
</script>

<template>
  <component :is="to ? 'RouterLink' : 'div'" :to="to" class="metric">
    <div class="metric-label"><component :is="icon" :size="18" aria-hidden="true" />{{ label }}</div>
    <div class="metric-value">{{ value }}</div>
    <div class="metric-hint" :class="{ bad }">{{ hint }}</div>
  </component>
</template>
