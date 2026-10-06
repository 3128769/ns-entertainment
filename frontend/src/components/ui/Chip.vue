<script setup lang="ts">
withDefaults(defineProps<{ tone?: 'warn' | 'blue' | 'ok' | 'violet' | 'muted'; as?: 'span' | 'button' }>(), { tone: 'muted', as: 'span' })
</script>

<template>
  <component :is="as" class="chip" :class="tone" :type="as === 'button' ? 'button' : undefined"><slot name="icon" /><slot /></component>
</template>
