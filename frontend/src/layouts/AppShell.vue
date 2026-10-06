<script setup lang="ts">
import { computed, ref, watch, type Component } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { Bell, Bot, History, LayoutGrid, LogOut, Menu, Moon, Radar, Server, Sun, Users } from '@lucide/vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { api } from '@/lib/api'
import { clearToken } from '@/lib/auth'
import { issues, refresh, store } from '@/lib/store'
import { theme, toggleTheme } from '@/lib/theme'

const route = useRoute()
const router = useRouter()
const menuOpen = ref(false)
watch(() => route.path, () => (menuOpen.value = false))

interface NavItem { to: string; label: string; icon: Component; count?: number; alert?: number }
const count = (n: number): number | undefined => (store.loaded ? n : undefined)
const groups = computed<{ label: string; items: NavItem[] }[]>(() => [
  { label: '工作台', items: [
    { to: '/', label: '总览', icon: LayoutGrid, alert: issues.value.length || undefined },
    { to: '/accounts', label: '签到账号', icon: Users, count: count(store.accounts.length) },
  ] },
  { label: '自动化', items: [
    { to: '/keywords', label: '关键词监听', icon: Radar, count: count(store.accounts.filter((a) => a.keyword_monitor_enabled).length) },
    { to: '/messages', label: '私信通知', icon: Bell, count: count(store.accounts.filter((a) => a.message_monitor_enabled).length) },
  ] },
  { label: '连接', items: [
    { to: '/proxies', label: '代理管理', icon: Server, count: count(store.proxies.length) },
    { to: '/bots', label: '通知设置', icon: Bot, count: count(store.bots.length) },
    { to: '/history', label: '执行记录', icon: History },
  ] },
])

const themeLabel = computed(() => (theme.value === 'dark' ? '切换到浅色' : '切换到深色'))

async function logout(): Promise<void> {
  try {
    await api.logout()
  } catch {
    /* the server session may already be gone */
  }
  clearToken()
  await router.replace('/')
}

const isActive = (to: string): boolean => (to === '/' ? route.path === '/' : route.path.startsWith(to))
const worker = computed(() => (!store.worker ? null : store.worker.ready ? 'ok' : 'bad'))
</script>

<template>
  <div class="app">
    <aside class="side" :class="{ open: menuOpen }" aria-label="主导航">
      <div class="brand">
        <span class="logo" aria-hidden="true">NS</span>
        <div><span class="brand-name">NodeSeek</span><span class="brand-sub">控制台</span></div>
      </div>
      <nav class="nav">
        <template v-for="group in groups" :key="group.label">
          <div class="nav-label">{{ group.label }}</div>
          <RouterLink v-for="item in group.items" :key="item.to" :to="item.to" class="nav-btn" :class="{ active: isActive(item.to) }" :aria-current="isActive(item.to) ? 'page' : undefined">
            <component :is="item.icon" :size="20" aria-hidden="true" />
            <span>{{ item.label }}</span>
            <span v-if="item.alert" class="nav-count alert" :title="`${item.alert} 项需要处理`">{{ item.alert }}</span>
            <span v-else-if="item.count !== undefined" class="nav-count">{{ item.count }}</span>
          </RouterLink>
        </template>
      </nav>
      <div v-if="worker" class="worker" :class="worker" :title="store.worker ? `并发 ${store.worker.concurrency ?? '-'} · 版本 ${store.worker.version}` : ''">
        <i /> {{ worker === 'ok' ? '后台服务运行中' : '后台服务未运行' }}
      </div>
      <div class="side-foot"><span>NodeSeek 娱乐中心</span><span class="version">v{{ store.worker?.version ?? '3.0.2' }}</span></div>
    </aside>
    <div class="scrim" :class="{ show: menuOpen }" @click="menuOpen = false" />

    <main class="main">
      <header class="top">
        <button class="top-btn menu-btn" type="button" aria-label="打开导航" @click="menuOpen = !menuOpen"><Menu :size="20" /></button>
        <span class="top-title">{{ route.meta.title }}</span>
        <div class="top-actions">
          <button class="top-btn" type="button" :title="themeLabel" :aria-label="themeLabel" @click="toggleTheme"><component :is="theme === 'dark' ? Sun : Moon" :size="20" /></button>
          <button class="top-btn" type="button" title="退出登录" aria-label="退出登录" @click="logout"><LogOut :size="20" /></button>
        </div>
      </header>

      <p v-if="store.error && store.loaded" class="load-warning" role="alert">刷新失败：{{ store.error }}。当前仍显示上次成功加载的数据。</p>
      <div class="content">
        <div v-if="!store.loaded && !store.error" class="panel boot" role="status">正在加载数据…</div>
        <div v-else-if="!store.loaded" class="panel boot err" role="alert">
          <p>{{ store.error }}</p>
          <BaseButton variant="primary" @click="refresh">重试</BaseButton>
        </div>
        <RouterView v-else />
      </div>
    </main>
  </div>
</template>

<style scoped>
.app { display: flex; min-height: 100dvh; }
.main { flex: 1; min-width: 0; }

.side { position: sticky; top: 0; flex: 0 0 256px; width: 256px; height: 100dvh; display: flex; flex-direction: column; background: var(--panel); border-right: 1px solid var(--line); }
.brand { display: flex; align-items: center; gap: 12px; height: 64px; flex: none; padding: 0 18px; border-bottom: 1px solid var(--line); }
.logo { display: grid; place-items: center; width: 28px; height: 28px; border-radius: 8px; background: var(--logo-bg); color: var(--logo-fg); font-size: 11px; font-weight: 700; }
.brand-name, .brand-sub { display: block; }
.brand-name { font-size: 14px; font-weight: 600; letter-spacing: -0.01em; }
.brand-sub { margin-top: 1px; font-size: 12px; color: var(--muted); }

.nav { flex: 1; padding: 8px 12px 12px; overflow-y: auto; }
.nav-label { margin: 14px 10px 6px; font-size: 11px; font-weight: 600; color: var(--muted); }
.nav-btn { display: flex; align-items: center; gap: 12px; width: 100%; height: 36px; margin-bottom: 4px; padding: 0 10px; border-radius: 8px; color: var(--sub); font-size: 13px; }
.nav-btn svg { color: var(--icon); }
.nav-btn:hover { background: var(--panel2); color: var(--text); }
.nav-btn.active { background: var(--accent-soft); color: var(--text); font-weight: 600; }
.nav-btn span:first-of-type { flex: 1; }
.nav-count { display: grid; place-items: center; min-width: 18px; height: 18px; padding: 0 5px; border-radius: 999px; background: var(--panel2); color: var(--muted); font-size: 11px; font-weight: 400; }
.nav-btn.active .nav-count { background: var(--panel); color: var(--text); }
.nav-count.alert { background: var(--badge-bad-bg); color: var(--badge-bad); border: 1px solid var(--badge-bad-line); font-weight: 600; }

.worker { display: flex; align-items: center; gap: 8px; margin: 0 18px 10px; font-size: 12px; color: var(--muted); }
.worker i { width: 7px; height: 7px; border-radius: 50%; background: var(--muted); }
.worker.ok i { background: #10b981; }
.worker.bad { color: var(--badge-bad); }
.worker.bad i { background: #f43f5e; }
.side-foot { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 14px 18px 16px; border-top: 1px solid var(--line); font-size: 12px; color: var(--muted); }
.version { padding: 2px 6px; border: 1px solid var(--line); border-radius: 5px; font: 11px var(--mono); color: var(--sub); white-space: nowrap; }

.top { position: sticky; top: 0; z-index: 20; display: flex; align-items: center; gap: 12px; height: 56px; padding: 0 32px; background: var(--top-bg); backdrop-filter: blur(12px); border-bottom: 1px solid var(--line); }
.top-actions { display: flex; gap: 2px; margin-left: auto; }
.top-btn { display: grid; place-items: center; width: 36px; height: 36px; padding: 0; border: 0; border-radius: 8px; background: transparent; color: var(--sub); }
.top-btn:hover { background: var(--panel2); color: var(--text); }
.menu-btn, .top-title { display: none; }
.top-title { font-size: 14px; font-weight: 600; }

.load-warning { margin: 14px 32px 0; padding: 9px 12px; border-radius: 8px; font-size: 12px; background: var(--badge-bad-bg); color: var(--badge-bad); border: 1px solid var(--badge-bad-line); }
.boot { display: grid; justify-items: center; gap: 12px; padding: 64px 16px; color: var(--sub); }
.boot.err { color: var(--badge-bad); }

.scrim { display: none; }
@media (max-width: 1023px) {
  .side { position: fixed; z-index: 40; inset: 0 auto 0 0; transform: translateX(-100%); visibility: hidden; transition: transform 0.2s, visibility 0.2s; }
  .side.open { transform: none; visibility: visible; }
  .scrim.show { display: block; position: fixed; inset: 0; z-index: 30; background: var(--scrim-nav); }
  .menu-btn, .top-title { display: grid; }
  .top-title { display: block; }
  .top { padding: 0 12px; }
  .load-warning { margin: 12px 20px 0; }
}
</style>
