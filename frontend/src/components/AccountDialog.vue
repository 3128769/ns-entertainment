<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Trash2 } from '@lucide/vue'
import Badge from './ui/Badge.vue'
import BaseButton from './ui/BaseButton.vue'
import Field from './ui/Field.vue'
import Modal from './ui/Modal.vue'
import Segmented from './ui/Segmented.vue'
import Tabs from './ui/Tabs.vue'
import TagInput from './ui/TagInput.vue'
import { api, ApiError } from '@/lib/api'
import { cookieState } from '@/lib/account'
import { blankForm, buildPayload, formFrom, hasChanges, validateForm, type AccountForm, type TabKey } from '@/lib/accountForm'
import { confirmAction } from '@/lib/confirm'
import { describe } from '@/lib/messages'
import { refresh, store } from '@/lib/store'
import { toast } from '@/lib/toast'
import type { Account } from '@/lib/types'

const props = defineProps<{ open: boolean; account: Account | null; tab?: TabKey }>()
const emit = defineEmits<{ close: [] }>()

const editing = computed(() => props.account !== null)
const form = reactive<AccountForm>(blankForm())
const tab = ref<TabKey>('basic')
const busy = ref(false)
const serverError = ref('')
const showErrors = ref(false)

watch(() => [props.open, props.account?.id] as const, ([open]) => {
  if (!open) return
  Object.assign(form, props.account ? formFrom(props.account) : blankForm())
  tab.value = props.tab ?? 'basic'
  serverError.value = ''
  showErrors.value = false
}, { immediate: true })
watch(() => props.tab, (next) => next && (tab.value = next))

const errors = computed(() => validateForm(form, editing.value ? 'edit' : 'create'))
const shown = computed(() => (showErrors.value ? errors.value : { fields: {}, tabs: {} }))
const dirty = computed(() => (editing.value ? hasChanges(form, props.account ?? undefined) : true))
const cookie = computed(() => (props.account ? cookieState(props.account) : null))

const tabItems = computed(() => [
  { value: 'basic' as const, label: '基本', alert: !!shown.value.tabs.basic },
  { value: 'schedule' as const, label: '签到计划', alert: !!shown.value.tabs.schedule },
  { value: 'keywords' as const, label: '关键词', alert: !!shown.value.tabs.keywords },
  { value: 'messages' as const, label: '私信', alert: !!shown.value.tabs.messages },
  { value: 'alerts' as const, label: '掉线通知', alert: !!shown.value.tabs.alerts },
])

const preview = computed(() => form.schedule_mode === 'range'
  ? `每天 ${form.schedule_start}–${form.schedule_end} 之间的某个时刻签到；具体时刻按日期和账号随机选定，当天内不变。`
  : `每天 ${form.schedule_time} 签到。`)

function pickBot(prefix: 'keyword' | 'message' | 'offline'): void {
  const bot = store.bots.find((b) => b.id === form[`${prefix}_bot_id`])
  if (bot?.chat_id && !form[`${prefix}_chat_id`].trim()) form[`${prefix}_chat_id`] = bot.chat_id
}

async function save(): Promise<void> {
  showErrors.value = true
  const first = (['basic', 'schedule', 'keywords', 'messages', 'alerts'] as TabKey[]).find((key) => errors.value.tabs[key])
  if (first) {
    tab.value = first
    return
  }
  busy.value = true
  serverError.value = ''
  try {
    const payload = buildPayload(form, props.account ?? undefined)
    const { account } = props.account ? await api.updateAccount(props.account.id, payload) : await api.createAccount(payload)
    toast.ok(props.account ? '账号已保存' : `已添加账号 ${account.name}`)
    await refresh()
    emit('close')
  } catch (error) {
    serverError.value = describe(error instanceof ApiError ? error.code : 'REQUEST_FAILED')
  } finally {
    busy.value = false
  }
}

async function remove(): Promise<void> {
  const account = props.account
  if (!account) return
  const ok = await confirmAction({ title: `删除账号“${account.name}”？`, message: '同时会取消它排队中的任务。已有的执行记录会保留，但账号和 Cookie 无法恢复。', confirmText: '删除账号', danger: true })
  if (!ok) return
  busy.value = true
  try {
    await api.deleteAccount(account.id)
    toast.ok('账号已删除')
    await refresh()
    emit('close')
  } catch (error) {
    toast.error(describe(error instanceof ApiError ? error.code : 'REQUEST_FAILED'))
  } finally {
    busy.value = false
  }
}

async function requestClose(): Promise<void> {
  if (busy.value) return
  if (editing.value && dirty.value && !(await confirmAction({ title: '放弃未保存的修改？', message: '关闭后这些修改会丢失。', confirmText: '放弃修改', danger: true }))) return
  emit('close')
}
</script>

<template>
  <Modal :open="open" :title="account ? `编辑 ${account.name}` : '添加签到账号'" :subtitle="account ? '修改后点击保存；只会提交你改动过的字段。' : '填写 NodeSeek Cookie 后即可自动签到，监听可稍后再开。'" @close="requestClose">
    <template #head-extra><Badge v-if="cookie" :tone="cookie.tone">{{ cookie.label }}</Badge></template>
    <template #tabs><Tabs v-model="tab" :items="tabItems" label="账号设置分区" /></template>

    <form id="account-form" novalidate @submit.prevent="save">
      <section v-show="tab === 'basic'">
        <Field label="账号名称" for="f-name" required :error="shown.fields.name"><input id="f-name" v-model="form.name" class="input" maxlength="64" placeholder="例如 主号" :aria-invalid="!!shown.fields.name" /></Field>
        <label class="check-line"><input v-model="form.enabled" type="checkbox" />启用账号（关闭后暂停自动签到与监听，Cookie 掉线检查仍会继续）</label>
        <Field label="NodeSeek Cookie" for="f-cookie" :required="!editing" :error="shown.fields.cookie" :hint="editing ? '已安全保存。留空保持不变；粘贴新的 Cookie 会替换它，并清除“已过期”标记。' : '登录 NodeSeek 后，在浏览器开发者工具的 Network 里复制任一请求头的 Cookie 整段，仅加密保存在服务器。'">
          <textarea id="f-cookie" v-model="form.cookie" class="input mono" rows="3" autocomplete="off" spellcheck="false" :placeholder="editing ? '留空保持不变' : '粘贴完整 Cookie'" :aria-invalid="!!shown.fields.cookie" />
        </Field>
        <Field label="代理线路" for="f-proxy" hint="签到、监听和掉线检查都会经由它访问 NodeSeek。">
          <select id="f-proxy" v-model="form.proxy_id" class="input">
            <option value="">直连</option>
            <option v-for="p in store.proxies" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
        </Field>
        <Field label="User-Agent" for="f-ua" hint="默认使用内置的桌面 Chrome，通常不需要修改。"><input id="f-ua" v-model="form.user_agent" class="input mono" maxlength="512" /></Field>
      </section>

      <section v-show="tab === 'schedule'">
        <Field label="时间模式"><Segmented v-model="form.schedule_mode" label="时间模式" :options="[{ value: 'fixed', label: '固定时间' }, { value: 'range', label: '随机时间区间' }]" /></Field>
        <Field v-if="form.schedule_mode === 'fixed'" label="签到时间" for="f-time" :error="shown.fields.schedule_time"><input id="f-time" v-model="form.schedule_time" class="input time" type="time" /></Field>
        <div v-else class="form-grid">
          <Field label="开始时间" for="f-start"><input id="f-start" v-model="form.schedule_start" class="input" type="time" /></Field>
          <Field label="结束时间" for="f-end" :error="shown.fields.schedule_end"><input id="f-end" v-model="form.schedule_end" class="input" type="time" :aria-invalid="!!shown.fields.schedule_end" /></Field>
        </div>
        <p class="preview">{{ preview }}（北京时间）</p>
        <Field label="手气模式" hint="随机手气每次收益不固定；固定手气每次收益相同。"><Segmented v-model="form.random_checkin" label="手气模式" :options="[{ value: true, label: '随机手气' }, { value: false, label: '固定手气' }]" /></Field>
      </section>

      <section v-show="tab === 'keywords'">
        <label class="check-line"><input v-model="form.keyword_monitor_enabled" type="checkbox" />启用关键词监听（约每 15 秒读取 RSS 新帖，标题含关键词时通知；首次启用只建立基线，不补发旧帖）</label>
        <Field label="关键词（最多 20 个）" for="f-keywords" :error="shown.fields.keywords" hint="回车、逗号或换行添加；不区分大小写和全半角。"><TagInput id="f-keywords" v-model="form.keywords" :max="20" placeholder="输入关键词后回车" /></Field>
        <div class="form-grid">
          <Field label="通知 Bot" for="f-kbot" :error="shown.fields.keyword_bot_id">
            <select id="f-kbot" v-model="form.keyword_bot_id" class="input" @change="pickBot('keyword')"><option value="">{{ store.bots.length ? '请选择' : '请先在“通知设置”添加 Bot' }}</option><option v-for="b in store.bots" :key="b.id" :value="b.id">{{ b.name }}</option></select>
          </Field>
          <Field label="Chat ID" for="f-kchat" :error="shown.fields.keyword_chat_id"><input id="f-kchat" v-model="form.keyword_chat_id" class="input" maxlength="64" placeholder="例如 123456789" /></Field>
        </div>
      </section>

      <section v-show="tab === 'messages'">
        <label class="check-line"><input v-model="form.message_monitor_enabled" type="checkbox" />启用私信通知（约每分钟读取官方私信列表，只通知别人发给你的）</label>
        <div class="form-grid">
          <Field label="通知 Bot" for="f-mbot" :error="shown.fields.message_bot_id">
            <select id="f-mbot" v-model="form.message_bot_id" class="input" @change="pickBot('message')"><option value="">{{ store.bots.length ? '请选择' : '请先在“通知设置”添加 Bot' }}</option><option v-for="b in store.bots" :key="b.id" :value="b.id">{{ b.name }}</option></select>
          </Field>
          <Field label="Chat ID" for="f-mchat" :error="shown.fields.message_chat_id"><input id="f-mchat" v-model="form.message_chat_id" class="input" maxlength="64" placeholder="例如 123456789" /></Field>
        </div>
      </section>

      <section v-show="tab === 'alerts'">
        <label class="check-line"><input v-model="form.offline_notify_enabled" type="checkbox" />Cookie 过期时通知 Telegram（每 5 分钟检查一次，同一个 Cookie 只提醒一次；开启后，自动签到成功也会通过这里发送收益通知）</label>
        <div class="form-grid">
          <Field label="通知 Bot" for="f-obot" :error="shown.fields.offline_bot_id">
            <select id="f-obot" v-model="form.offline_bot_id" class="input" @change="pickBot('offline')"><option value="">{{ store.bots.length ? '请选择' : '请先在“通知设置”添加 Bot' }}</option><option v-for="b in store.bots" :key="b.id" :value="b.id">{{ b.name }}</option></select>
          </Field>
          <Field label="Chat ID" for="f-ochat" :error="shown.fields.offline_chat_id"><input id="f-ochat" v-model="form.offline_chat_id" class="input" maxlength="64" placeholder="例如 123456789" /></Field>
        </div>
      </section>

      <p v-if="serverError" class="form-error" role="alert">{{ serverError }}</p>
    </form>

    <template #footer>
      <BaseButton v-if="editing" variant="danger" :disabled="busy" @click="remove"><template #icon><Trash2 :size="15" /></template>删除</BaseButton>
      <span class="spacer" />
      <BaseButton :disabled="busy" @click="requestClose">取消</BaseButton>
      <BaseButton variant="primary" type="submit" form="account-form" :loading="busy" :disabled="editing && !dirty">{{ editing ? '保存账号' : '添加账号' }}</BaseButton>
    </template>
  </Modal>
</template>

<style scoped>
.time { max-width: 180px; }
.preview { margin: -2px 0 14px; padding: 9px 11px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel2); color: var(--sub); font-size: 12px; line-height: 1.6; }
.spacer { flex: 1; }
.check-line { align-items: flex-start; line-height: 1.6; }
.check-line input { margin-top: 2px; flex: none; }
textarea.mono { font-size: 12px; }
</style>
