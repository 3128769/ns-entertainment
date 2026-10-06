<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Bell, ChevronRight, CircleAlert, Cookie, History, Plus, Radar, Server, TriangleAlert, Users } from '@lucide/vue'
import ActivityRows from '@/components/ActivityRows.vue'
import MetricCard from '@/components/MetricCard.vue'
import PageHead from '@/components/PageHead.vue'
import StatusRow from '@/components/StatusRow.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { cookieState } from '@/lib/account'
import { issues, store } from '@/lib/store'
import { relativeTime } from '@/lib/time'

const router = useRouter()
const accounts = computed(() => store.accounts)
const valid = computed(() => accounts.value.filter((a) => cookieState(a).key === 'valid').length)
const expired = computed(() => accounts.value.filter((a) => cookieState(a).key === 'expired').length)
const enabled = computed(() => accounts.value.filter((a) => a.enabled))
const week = computed(() => {
  const cutoff = Date.now() - 7 * 86400000
  return store.recent.checkin.filter((r) => (r.status === 'success' || r.status === 'already') && new Date(r.ran_at).getTime() > cutoff).length
})
const keywords = computed(() => accounts.value.filter((a) => a.keyword_monitor_enabled).length)
const messages = computed(() => accounts.value.filter((a) => a.message_monitor_enabled).length)
const proxied = computed(() => accounts.value.filter((a) => a.proxy_id).length)
const lastMatch = computed(() => accounts.value.map((a) => a.last_match_at).filter((v): v is string => !!v).sort().at(-1) ?? null)

function fix(issue: { accountId?: string; tab?: string }): void {
  if (issue.accountId) void router.push({ path: '/accounts', query: { edit: issue.accountId, ...(issue.tab ? { tab: issue.tab } : {}) } })
}
</script>

<template>
  <PageHead>
    <BaseButton variant="primary" @click="router.push({ path: '/accounts', query: { new: '1' } })"><template #icon><Plus :size="16" /></template>添加账号</BaseButton>
  </PageHead>

  <section v-if="issues.length" class="panel attention" aria-label="需要处理">
    <div class="panel-head">
      <div><div class="panel-title">需要处理</div><div class="panel-desc">先处理红色项，它们会让签到或监听停摆</div></div>
      <span class="panel-count">{{ issues.length }} 项</span>
    </div>
    <div v-for="issue in issues" :key="issue.id" class="issue">
      <component :is="issue.severity === 'bad' ? CircleAlert : TriangleAlert" :size="18" :class="issue.severity" aria-hidden="true" />
      <div class="txt">
        <div class="t">{{ issue.title }}</div>
        <div class="d">{{ issue.detail }}</div>
      </div>
      <BaseButton v-if="issue.accountId" variant="action" @click="fix(issue)">去处理</BaseButton>
    </div>
  </section>

  <div class="metrics">
    <MetricCard label="Cookie 有效" :value="valid" :icon="Cookie" :hint="expired ? `${expired} 个已过期` : '没有过期账号'" :bad="expired > 0" to="/accounts" />
    <MetricCard label="签到账号" :value="enabled.length" :icon="Users" :hint="`共 ${accounts.length} 个账号`" to="/accounts" />
    <MetricCard label="近 7 天成功" :value="week" :icon="History" hint="当前已加载的签到记录" to="/history" />
    <MetricCard label="关键词监听" :value="keywords" :icon="Radar" :hint="lastMatch ? `最近命中 ${relativeTime(lastMatch)}` : '按原帖发布时间检查'" to="/keywords" />
    <MetricCard label="私信通知" :value="messages" :icon="Bell" hint="按官方私信列表检查" to="/messages" />
    <MetricCard label="代理线路" :value="store.proxies.length" :icon="Server" :hint="`${proxied} 个账号使用`" to="/proxies" />
  </div>

  <div class="section-heading">
    <h2><Users :size="20" />账号状态</h2>
    <RouterLink to="/accounts" class="text-link">管理账号 <ChevronRight :size="14" /></RouterLink>
  </div>
  <div class="status-list">
    <StatusRow v-for="a in accounts" :key="a.id" :account="a" @edit="router.push({ path: '/accounts', query: { edit: a.id } })" />
    <div v-if="!accounts.length" class="panel empty">暂无签到账号，点击“添加账号”开始配置。</div>
  </div>

  <div class="history-grid">
    <section class="panel">
      <div class="panel-head"><div><div class="panel-title">最近签到</div><div class="panel-desc">最近 5 条签到执行结果</div></div></div>
      <ActivityRows :items="store.recent.checkin" kind="checkin" :limit="5" />
    </section>
    <section class="panel">
      <div class="panel-head"><div><div class="panel-title">最近关键词检查</div><div class="panel-desc">最近 5 条命中、通知与失败记录</div></div></div>
      <ActivityRows :items="store.recent.monitor" kind="monitor" :limit="5" />
    </section>
  </div>
  <div class="history-more">
    <RouterLink to="/history" class="text-link">查看全部签到记录 <ChevronRight :size="14" /></RouterLink>
    <RouterLink to="/keywords" class="text-link">查看关键词记录 <ChevronRight :size="14" /></RouterLink>
    <RouterLink to="/messages" class="text-link">查看私信记录 <ChevronRight :size="14" /></RouterLink>
  </div>
</template>

<style scoped>
.attention { margin-bottom: 22px; }
.issue { display: flex; align-items: center; gap: 12px; padding: 12px 16px; border-bottom: 1px solid var(--line); }
.issue:last-child { border-bottom: 0; }
.issue .bad { color: var(--red); }
.issue .warn { color: var(--chip-warn); }
.txt { flex: 1; min-width: 0; }
.t { font-size: 13px; font-weight: 500; }
.d { margin-top: 2px; font-size: 12px; color: var(--sub); overflow-wrap: anywhere; }
@media (max-width: 560px) { .issue { flex-wrap: wrap; } .txt { flex-basis: calc(100% - 32px); } }

.status-list { display: grid; gap: 10px; margin-bottom: 20px; }
.history-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-top: 22px; }
.history-grid .panel + .panel { margin-top: 0; }
@media (max-width: 960px) { .history-grid { grid-template-columns: 1fr; } }
.history-more { display: flex; justify-content: flex-end; gap: 18px; flex-wrap: wrap; padding: 10px 16px; }
</style>
