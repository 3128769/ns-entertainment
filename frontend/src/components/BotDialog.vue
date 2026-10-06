<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import BaseButton from './ui/BaseButton.vue'
import Field from './ui/Field.vue'
import Modal from './ui/Modal.vue'
import { api, ApiError } from '@/lib/api'
import { describe } from '@/lib/messages'
import { refresh } from '@/lib/store'
import { toast } from '@/lib/toast'
import type { Bot } from '@/lib/types'

const props = defineProps<{ open: boolean; bot: Bot | null }>()
const emit = defineEmits<{ close: [] }>()

const form = reactive({ name: '', chat_id: '', token: '' })
const busy = ref(false)
const error = ref('')
const editing = computed(() => props.bot !== null)

watch(() => props.open, (open) => {
  if (!open) return
  form.name = props.bot?.name ?? ''
  form.chat_id = props.bot?.chat_id ?? ''
  form.token = ''
  error.value = ''
}, { immediate: true })

async function save(): Promise<void> {
  const name = form.name.trim(), chat = form.chat_id.trim(), token = form.token.trim()
  if (!name || !chat || (!editing.value && !token.includes(':')) || (token && !token.includes(':'))) {
    error.value = describe('BOT_FIELDS_INVALID')
    return
  }
  busy.value = true
  error.value = ''
  try {
    await api.saveBot({ name, chat_id: chat, token, ...(props.bot ? { bot_id: props.bot.id } : {}) })
    toast.ok(editing.value ? 'Bot 已保存' : 'Bot 已添加')
    await refresh()
    emit('close')
  } catch (e) {
    error.value = describe(e instanceof ApiError ? e.code : 'REQUEST_FAILED')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <Modal :open="open" :width="480" :title="editing ? '编辑通知 Bot' : '添加通知 Bot'" subtitle="Telegram Bot 用来把命中和告警发给你" @close="!busy && emit('close')">
    <form id="bot-form" class="form" novalidate @submit.prevent="save">
      <Field label="名称" for="b-name" required><input id="b-name" v-model="form.name" class="input" maxlength="64" placeholder="例如：NS 通知" /></Field>
      <Field label="默认接收人 Chat ID" for="b-chat" required hint="个人 ID 或群组 ID。选择此 Bot 时会作为默认值填入账号设置。先在 Telegram 里向 Bot 发送 /start。">
        <input id="b-chat" v-model="form.chat_id" class="input mono" maxlength="64" placeholder="例如：123456789" />
      </Field>
      <Field label="Bot Token" for="b-token" :required="!editing"  :hint="editing ? '已安全保存。留空保持不变，填写则替换。' : '从 @BotFather 获取，形如 123456:ABC-DEF…，加密保存在服务器。'">
        <input id="b-token" v-model="form.token" class="input mono" type="password" autocomplete="off" maxlength="512" :placeholder="editing ? '••••••••（留空保持不变）' : '123456:ABC…'" />
      </Field>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </form>
    <template #footer>
      <BaseButton :disabled="busy" @click="emit('close')">取消</BaseButton>
      <BaseButton variant="primary" type="submit" form="bot-form" :loading="busy">保存</BaseButton>
    </template>
  </Modal>
</template>

<style scoped>
.form { display: grid; }
.error { padding: 9px 12px; border-radius: 8px; background: var(--badge-bad-bg); border: 1px solid var(--badge-bad-line); color: var(--badge-bad); font-size: 12px; }
</style>
