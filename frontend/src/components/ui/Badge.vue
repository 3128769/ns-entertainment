<script setup lang="ts">
import type { Tone } from '@/lib/messages'

withDefaults(defineProps<{ tone?: Tone; dot?: boolean }>(), { tone: 'muted', dot: true })
</script>

<template>
  <span class="badge" :class="tone"><i v-if="dot" class="badge-dot" aria-hidden="true" /><slot /></span>
</template>
