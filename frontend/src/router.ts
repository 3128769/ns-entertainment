import { createRouter, createWebHistory } from 'vue-router'

export const routes = [
  { path: '/', name: 'overview', component: () => import('./views/OverviewView.vue'), meta: { title: '总览', desc: '先确认 Cookie，再查看签到、关键词、私信和掉线' } },
  { path: '/accounts', name: 'accounts', component: () => import('./views/AccountsView.vue'), meta: { title: '签到账号', desc: '管理签到计划与三类通知规则' } },
  { path: '/keywords', name: 'keywords', component: () => import('./views/RulesView.vue'), props: { kind: 'keywords' }, meta: { title: '关键词监听', desc: '管理关键词规则、通知与检查失败' } },
  { path: '/messages', name: 'messages', component: () => import('./views/RulesView.vue'), props: { kind: 'messages' }, meta: { title: '私信通知', desc: '管理私信规则、通知与检查失败' } },
  { path: '/proxies', name: 'proxies', component: () => import('./views/ProxiesView.vue'), meta: { title: '代理管理', desc: '管理签到与监听使用的出口线路' } },
  { path: '/bots', name: 'bots', component: () => import('./views/BotsView.vue'), meta: { title: '通知设置', desc: '管理 Telegram 通知目标' } },
  { path: '/history', name: 'history', component: () => import('./views/HistoryView.vue'), meta: { title: '执行记录', desc: '查看最近签到结果' } },
  { path: '/:rest(.*)*', redirect: '/' },
]

export const router = createRouter({ history: createWebHistory(), routes })

router.afterEach((to) => {
  const title = to.meta.title as string | undefined
  document.title = title ? `${title} · NodeSeek 娱乐中心` : 'NodeSeek 娱乐中心'
})
