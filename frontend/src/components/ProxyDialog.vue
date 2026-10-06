<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import BaseButton from './ui/BaseButton.vue'
import Field from './ui/Field.vue'
import Modal from './ui/Modal.vue'
import { api, ApiError } from '@/lib/api'
import { describe } from '@/lib/messages'
import { refresh } from '@/lib/store'
import { toast } from '@/lib/toast'
import type { Proxy } from '@/lib/types'

const props = defineProps<{ open: boolean; proxy: Proxy | null }>()
const emit = defineEmits<{ close: [] }>()

const form = reactive({ name: '', proxy_url: '', remark: '' })
const busy = ref(false)
const error = ref('')
const editing = computed(() => props.proxy !== null)

watch(() => props.open, (open) => {
  if (!open) return
  form.name = props.proxy?.name ?? ''
  form.remark = props.proxy?.remark ?? ''
  form.proxy_url = ''
  error.value = ''
}, { immediate: true })

async function save(): Promise<void> {
  const name = form.name.trim(), url = form.proxy_url.trim()
  if (!name) return void (error.value = describe('PROXY_NAME_INVALID'))
  if (!editing.value && !url) return void (error.value = describe('PROXY_URL_INVALID'))
  busy.value = true
  error.value = ''
  try {
    const body = { name, remark: form.remark.trim(), ...(url ? { proxy_url: url } : {}) }
    if (props.proxy) await api.updateProxy(props.proxy.id, body)
    else await api.createProxy(body)
    toast.ok(editing.value ? '代理已保存' : '代理已添加')
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
  <Modal :open="open" :width="480" :title="editing ? '编辑代理' : '添加代理'" subtitle="账号可以选择经由代理访问 NodeSeek" @close="!busy && emit('close')">
    <form id="proxy-form" class="form" novalidate @submit.prevent="save">
      <Field label="名称" for="p-name" required><input id="p-name" v-model="form.name" class="input" maxlength="64" placeholder="例如：香港出口" /></Field>
      <Field label="代理链接" for="p-url" :required="!editing" :hint="editing ? '链接含账号密码，保存后不再显示。留空保持不变。' : '支持 socks5://、socks4://、http://，也可写成 host:port:user:password。'">
        <input id="p-url" v-model="form.proxy_url" class="input mono" autocomplete="off" spellcheck="false" maxlength="2048" :placeholder="editing ? '留空保持不变' : 'socks5://user:password@host:port'" />
      </Field>
      <Field label="备注" for="p-remark"><input id="p-remark" v-model="form.remark" class="input" maxlength="240" placeholder="线路说明（可选）" /></Field>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </form>
    <template #footer>
      <BaseButton :disabled="busy" @click="emit('close')">取消</BaseButton>
      <BaseButton variant="primary" type="submit" form="proxy-form" :loading="busy">保存</BaseButton>
    </template>
  </Modal>
</template>

<style scoped>
.form { display: grid; }
.error { padding: 9px 12px; border-radius: 8px; background: var(--badge-bad-bg); border: 1px solid var(--badge-bad-line); color: var(--badge-bad); font-size: 12px; }
</style>
