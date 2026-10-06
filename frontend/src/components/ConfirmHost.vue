<script setup lang="ts">
import { computed } from 'vue'
import { confirmState, settleConfirm } from '@/lib/confirm'
import BaseButton from './ui/BaseButton.vue'
import Modal from './ui/Modal.vue'

const current = computed(() => confirmState.current)
</script>

<template>
  <Modal :open="!!current" :title="current?.title ?? ''" :width="420" @close="settleConfirm(false)">
    <p v-if="current?.message" class="message">{{ current.message }}</p>
    <template #footer>
      <BaseButton @click="settleConfirm(false)">取消</BaseButton>
      <BaseButton :variant="current?.danger ? 'danger' : 'primary'" autofocus @click="settleConfirm(true)">{{ current?.confirmText ?? '确定' }}</BaseButton>
    </template>
  </Modal>
</template>

<style scoped>
.message { color: var(--sub); font-size: 13px; line-height: 1.6; }
</style>
