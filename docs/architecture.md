# 架构

## 运行边界

同一个镜像、两个角色：

| 角色 | 命令 | 职责 |
| --- | --- | --- |
| `web` | `uvicorn nsapp.api.app:app` | JSON API、登录、托管前端静态文件。**不**调度、不执行任务 |
| `worker` | `python -m nsapp.worker.main` | 唯一的调度器；领取并执行任务；每 5 秒写心跳 |

数据（SQLite、实例密钥、管理员密码文件）都在 `/data`，两个角色共享。不要给一个实例起多个 Worker，也不要增加 uvicorn 进程来“扩容”——任务一致性依赖单 Worker。

## 代码分层（`backend/nsapp`）

依赖方向只能向下：

```
api  ─►  services  ─►  repositories  ─►  db / schema
              │              ▲
              ├─► integrations (NodeSeek / Telegram / 代理探测，只做 HTTP)
              └─► domain      (纯规则：账号校验、调度计划，不读库不联网)
tasks (签到 / 关键词 / 私信 / Cookie 检查)  ─►  services + integrations
worker (调度循环、租约、并发)               ─►  tasks + repositories
```

- **domain**：`accounts.normalize`（配置校验）、`schedule.plan_jobs`（给定账号和当前时间，算出此刻需要入队哪些任务；纯函数，可用固定时钟测试）。
- **repositories**：`records`（账号/代理/Bot 的 JSON 文档表，字段级合并写入）、`jobs`（带租约的任务队列）、`notifications`（Telegram 投递账本）、`history`、`users`。
- **tasks**：每种任务一个模块，入口 `run(account_id, source) -> result`。结果字典就是写进历史、返回给界面的那一份。
- **api**：只做解析、调用服务、返回结果；业务失败统一是 `AppError(code)`，由应用层转成 `{"detail": CODE}` 和 HTTP 状态码。前端把 code 翻译成中文（`frontend/src/lib/messages.ts`）。

## 任务语义（3.0 沿用 2.0 的全部保证）

- **幂等入队**：`(账号, 类型, 周期键)` 唯一；同一账号同一类型最多一个待执行任务。
- **租约**：领取任务时建 90 秒租约，Worker 每 5 秒续租。同一账号同一时刻只有一个运行中的任务，不同账号并行（默认并发 4）。
- **外部写阶段**：发出签到或 Telegram 请求之前把任务标记为 `external_write`。若此时 Worker 崩溃或请求超时，结果记为 `uncertain`（待核实），**不会**自动重发——请求可能已经成功。只有读操作（RSS、私信列表、Cookie 检查）和尚未发出请求的任务才会重试，最多 3 次，指数退避。
- **租约丢失即停写**：所有写库路径在事务内校验当前任务仍持有租约，旧 Worker 不能覆盖新 Worker 的结果。
- **通知防重**：每条通知有确定的事件键，账本保证至多发送一次；发送中崩溃或回包无法确认记为 `uncertain`，不会盲目重发。
- **结果写回只改自己的字段**：任务结束时只提交它改动过的字段；若期间用户替换了 Cookie，这次结果属于旧 Cookie，直接丢弃。
- **网络请求期间不持有数据库写事务。**

## 数据

SQLite（WAL），迁移 `0001`：

- `accounts` / `proxies` / `bots`：每行一个 JSON 文档（`record_json`），加 `id`、规范化名称（唯一）、`revision` 列。新增字段无需迁移。
- `jobs`、`notifications`、`task_history`、`worker_state`。
- `users`、`sessions`：早于 Alembic 存在，启动时幂等创建。会话令牌只存 SHA-256；登录时顺带清理过期会话。

Cookie、代理凭据、Bot Token、通知正文使用实例密钥（`/data/.secret_key`）做 Fernet 加密。API 永远不回传这些值。

## 可观测性

- `X-Request-ID` 贯穿请求与任务日志；日志只含 ID、状态码、耗时、错误码，不含 Cookie/Token/通知正文（白名单字段，错误码必须是 `UPPER_SNAKE` 才会输出）。
- `/healthz` 进程存活；`/readyz` 还要求迁移完成且 Worker 心跳有效；`GET /api/system/tasks`（登录后）给出队列和 Worker 状态，界面左下角据此显示“后台服务运行中/未运行”。

## 3.0 相对 2.0 的行为变化

见 [docs/releases/v3.0.0.md](releases/v3.0.0.md)。
