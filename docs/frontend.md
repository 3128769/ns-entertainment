# 前端

Vue 3（组合式 API）+ TypeScript + Vite + vue-router。没有 UI 框架，组件都在 `src/components`；构建产物是带内容哈希的静态文件，由 API 进程托管（`/assets/*` 长期缓存，`index.html` 不缓存）。

## 目录

```
src/
  lib/        api.ts（带类型的接口）· store.ts（全局状态、30 秒自动刷新、一键操作）· account.ts（Cookie 状态/任务健康/需处理项）
              accountForm.ts（编辑表单：只提交改动字段、校验）· messages.ts（状态与错误码的中文）· time.ts（一律北京时间）
  components/ 业务组件（AccountCard、StatusRow、HistoryPanel、AccountDialog…）与 ui/（按钮、徽标、标签、弹窗…）
  views/      七个页面：总览 / 签到账号 / 关键词监听 / 私信通知 / 代理管理 / 通知设置 / 执行记录
  styles/     tokens.css（设计令牌，明暗两套）· base.css · ui.css（面板、指标卡、徽标、标签等共用外观）
```

## 视觉风格

外观沿用 2.0 的设计，**令牌值与旧界面一致**（`tokens.css`）：zinc 中性色、发丝线边框、黑色主按钮与黑色 NS 方标、14px 圆角卡片、胶囊徽标与橙/蓝/绿/紫彩色标签、灰底任务格；深色主题逐项对应。改动外观时请先对照这些令牌，不要引入新的强调色。

## 行为

- 数据每 30 秒自动刷新（页面可见时），切回标签页若数据超过 15 秒也会刷新；页头可手动刷新。
- 编辑账号是一个带分页签的弹窗，只提交改动过的字段；“关键词/私信/掉线通知”等入口可直接深链到对应分页签：`/accounts?edit=<id>&tab=keywords`、`/accounts?new=1`。
- 本地令牌沿用 `ns_token`、主题沿用 `ns_theme_v4`，升级后无需重新登录。

## 开发

```bash
npm ci
npm run dev        # 代理 /api 到 http://127.0.0.1:8090（NS_BACKEND 可改）
npm test           # vitest：账号状态推导、表单、文案、时间
npm run build      # vue-tsc 类型检查 + vite 构建
```
