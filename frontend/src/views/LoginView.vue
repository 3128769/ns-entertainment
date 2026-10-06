<script setup lang="ts">
import { ref } from 'vue'
import { Loader2 } from '@lucide/vue'
import { api, ApiError } from '@/lib/api'
import { setToken } from '@/lib/auth'
import { describe } from '@/lib/messages'

const username = ref('')
const password = ref('')
const busy = ref(false)
const error = ref('')

async function submit(): Promise<void> {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    const { access_token } = await api.login(username.value.trim(), password.value)
    setToken(access_token)
  } catch (e) {
    error.value = describe(e instanceof ApiError ? e.code : 'REQUEST_FAILED')
    password.value = ''
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main class="login">
    <form class="box" @submit.prevent="submit">
      <div class="logo" aria-hidden="true">NS</div>
      <h1>NodeSeek 控制台</h1>
      <p class="lead">管理签到、监听和通知。Cookie 过期会直接标出。</p>

      <div class="field">
        <label for="login-username">用户名</label>
        <input id="login-username" v-model="username" class="input" name="username" autocomplete="username" autocapitalize="off" spellcheck="false" required autofocus />
      </div>
      <div class="field">
        <label for="login-password">密码</label>
        <input id="login-password" v-model="password" class="input" name="password" type="password" autocomplete="current-password" required />
      </div>

      <p v-if="error" class="error" role="alert">{{ error }}</p>

      <button class="submit" type="submit" :disabled="busy || !username || !password">
        <Loader2 v-if="busy" :size="16" class="spin" aria-hidden="true" />
        {{ busy ? '登录中…' : '登录' }}
      </button>
      <div class="version">NodeSeek 娱乐中心 · v3.0.4</div>
    </form>
  </main>
</template>

<style scoped>
.login { min-height: 100dvh; display: grid; place-items: center; padding: 24px 16px; }
.box { width: min(380px, 100%); padding: 28px 24px 24px; display: grid; gap: 14px; background: var(--panel); border: 1px solid var(--line); border-radius: var(--r-lg); box-shadow: var(--shadow); }
.logo { display: grid; place-items: center; width: 36px; height: 36px; border-radius: 10px; background: var(--logo-bg); color: var(--logo-fg); font-size: 13px; font-weight: 700; }
h1 { font-size: 20px; line-height: 26px; font-weight: 600; letter-spacing: -0.02em; }
.lead { margin-top: -8px; color: var(--sub); font-size: 13px; }
.field { margin: 0; }
.error { padding: 9px 12px; border-radius: 8px; background: var(--badge-bad-bg); border: 1px solid var(--badge-bad-line); color: var(--badge-bad); font-size: 12px; }
.submit { display: inline-flex; align-items: center; justify-content: center; gap: 8px; height: 38px; border: 0; border-radius: 8px; background: var(--black); color: var(--on-black); font-size: 13px; font-weight: 500; }
.submit:hover:not(:disabled) { opacity: 0.88; }
.submit:disabled { opacity: 0.5; }
.version { text-align: center; color: var(--muted); font-size: 11px; }
</style>
