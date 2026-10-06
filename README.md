[![ci](https://github.com/3128769/ns-entertainment/actions/workflows/ci.yml/badge.svg)](https://github.com/3128769/ns-entertainment/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

# NodeSeek 娱乐中心

单租户的 NodeSeek 管理程序，自己部署、自己用：

- **每日签到**：固定时间或随机时间区间，随机/固定手气，支持每个账号单独的代理
- **关键词监听**：读取 NodeSeek 的 RSS 新帖，标题命中关键词就发 Telegram
- **私信通知**：新私信即时转发到 Telegram
- **Cookie 掉线提醒**：Cookie 过期时只提醒一次；签到结果不确定时标记“待核实”，**绝不自动重复签到**

## 界面

截图使用演示用的假数据。

![总览](docs/images/overview.png)

![签到账号](docs/images/accounts.png)

![深色主题](docs/images/accounts-dark.png)

## 目录

```
frontend/   Vue 3 + TypeScript + Vite 单页应用（构建产物由 API 进程托管）
backend/    Python 3.12 · FastAPI · SQLAlchemy · SQLite（WAL）
deploy/     nginx 配置模板
docs/       架构、部署与回滚、前端、发布说明
```

同一个镜像有两个角色：`web`（API 和页面）和 `worker`（唯一的调度器与任务执行者）。

## 搭建需要什么

| 需要 | 说明 |
| --- | --- |
| 一台 Linux 服务器 | 装好 Docker 和 Docker Compose v2；两个容器各限 1GB 内存，512MB 以上空闲即可 |
| 出网访问 | `www.nodeseek.com`、`rss.nodeseek.com`、`api.telegram.org`。被 Cloudflare 拦截或直连不通时，可在界面里给账号配置 socks5/http 代理 |
| NodeSeek 账号 Cookie | 见下方“获取 Cookie” |
| Telegram Bot | 见下方“获取 Bot Token 和 Chat ID”（只用签到可不配） |
| 反向代理 + HTTPS（强烈建议） | 登录令牌走明文 HTTP 会被截获。可以用 `deploy/nginx.conf` 作为模板；没有域名时先用 SSH 隧道访问 `127.0.0.1:8090` |

## 快速开始

在服务器上新建一个文件夹，放入下面两个文件，再启动。**不需要下载源码，也不需要构建。**

**1. `docker-compose.yml`**：通用配置，每个环境变量都在注释里说明（同一份也在仓库里的 [docker-compose.template.yml](docker-compose.template.yml)）。

```yaml
# NodeSeek 娱乐中心 · 通用 docker-compose.yml
#
# 用法（在服务器上）：
#   1. 新建一个文件夹，把本文件保存成 docker-compose.yml
#   2. 在同一个文件夹里新建 .env，写一行管理员密码（至少 8 位，不要含 $）：
#        NS_ADMIN_PASSWORD=你的密码
#      想改本机端口，可以再加一行：NS_PORT=8090
#   3. 启动：docker compose up -d
#
# 管理员用户名是 admin。程序只监听服务器本机的 127.0.0.1:8090，不对公网开放：
# 用 nginx 做 HTTPS 反向代理（模板见 deploy/nginx.conf），或者用 SSH 隧道访问。
# 更新：docker compose pull && docker compose up -d
# 数据（数据库和加密密钥）保存在 Docker 卷 ns-data 里，备份时必须一起保存。

x-ns: &ns
  image: ghcr.io/3128769/ns-entertainment:latest   # 想固定版本就改成具体版本号，例如 :3.0.3
  restart: unless-stopped
  volumes:
    - ns-data:/data
  environment: &env
    TZ: Asia/Shanghai          # 调度和界面显示固定使用北京时间，不用改
    NS_DATA_DIR: /data         # 数据目录：SQLite 数据库、加密密钥、管理员密码文件
    NS_ADMIN_USER: admin       # 管理员用户名，只在第一次创建时使用
    # 管理员初始密码（来自 .env），只在第一次创建管理员时生效；留空则随机生成，写入 /data/.admin_password
    NS_ADMIN_PASSWORD: "${NS_ADMIN_PASSWORD:-}"
    NS_JOB_CONCURRENCY: "4"    # 后台任务并发数，1–16
    # 加密 Cookie、代理凭据、Bot Token 的实例密钥。默认自动生成并保存在数据卷里（/data/.secret_key），
    # 一般不用设置；必须和数据库一起备份，丢失后这些内容无法解密
    # NS_SECRET_KEY: ""
  read_only: true
  tmpfs: [/tmp]
  security_opt: [no-new-privileges:true]
  cap_drop: [ALL]
  init: true
  logging:
    driver: json-file
    options: { max-size: "10m", max-file: "3" }
  mem_limit: 1g
  cpus: 1.0

services:
  # 一次性任务：建表并生成加密密钥。每次启动都会先跑一遍，重复执行没有副作用
  migrate:
    <<: *ns
    command: ["python", "-m", "nsapp.cli", "migrate"]
    restart: "no"

  # 网页和接口
  web:
    <<: *ns
    command: ["uvicorn", "nsapp.api.app:app", "--host", "0.0.0.0", "--port", "8090"]
    depends_on:
      migrate:
        condition: service_completed_successfully
    ports:
      - "127.0.0.1:${NS_PORT:-8090}:8090"
    environment:
      <<: *env
      NS_SCHEDULER_ENABLED: "0"   # web 必须是 0：整个系统只能有一个 worker 负责调度
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/healthz', timeout=3)"]
      interval: 30s
      timeout: 5s
      start_period: 20s
      retries: 3

  # 后台任务：签到、关键词监听、私信通知（整个系统只能有一个）
  worker:
    <<: *ns
    command: ["python", "-m", "nsapp.worker.main"]
    depends_on:
      migrate:
        condition: service_completed_successfully
    environment:
      <<: *env
      NS_SCHEDULER_ENABLED: "1"
    healthcheck:
      test: ["CMD", "python", "-c", "from nsapp.repositories.jobs import state; raise SystemExit(0 if state()['ready'] else 1)"]
      interval: 30s
      timeout: 5s
      start_period: 10s
      retries: 3

volumes:
  ns-data:
```

**2. `.env`**：放在同一个文件夹，只写一行管理员密码（至少 8 位，不要含 `$`）。

```
NS_ADMIN_PASSWORD=你的密码
```

**3. 启动**：

```bash
docker compose up -d
curl http://127.0.0.1:8090/readyz        # 返回 {"status":"ok","ready":true} 即就绪
```

管理员用户名是 `admin`，密码就是 `.env` 里的 `NS_ADMIN_PASSWORD`（只在第一次创建管理员时生效）。更新到新版本：`docker compose pull && docker compose up -d`。

然后打开页面登录，按顺序配置：

1. **通知设置** → 添加 Bot（名称、Chat ID、Token），点“检查连接”校验（只校验，不发消息）。
2. **签到账号** → 添加账号，粘贴 Cookie，设置签到时间。
3. 按需在账号里开启 **关键词监听**、**私信通知**、**掉线通知**（每项需要选择 Bot 和接收人 Chat ID）。

### 修改管理员密码

```bash
docker compose run --rm --no-deps web python -m nsapp.cli set-admin-password
```

按提示输入两次新密码（至少 8 位）。修改后该账号所有已登录的会话会立即失效。`.env` 里的密码只在第一次创建管理员时用，改过之后可以删掉那一行。

### 获取 Cookie

登录 NodeSeek → 浏览器开发者工具（F12）→ Network → 点任意一个发往 `www.nodeseek.com` 的请求 → Request Headers 里的 `Cookie`，复制**整段**。Cookie 会过期，过期后总览页会提示，更新即可。

### 获取 Bot Token 和 Chat ID

1. 在 Telegram 里找 `@BotFather`，发送 `/newbot` 按提示创建，得到 Token（形如 `123456:ABC-DEF…`）。
2. 先给你的 Bot 发一条 `/start`（Bot 无法主动联系没有发过消息的人）。
3. 个人 Chat ID：找 `@userinfobot` 获取；或访问 `https://api.telegram.org/bot<Token>/getUpdates`，在返回里找 `chat.id`。群组的 Chat ID 是负数，需要先把 Bot 拉进群。

## 备份、升级、回滚

见 [docs/deployment.md](docs/deployment.md)。备份时数据库和加密密钥（`.secret_key`）要一起保存。

## 开发

```bash
# 后端
cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q

# 前端
cd frontend && npm ci && npm test && npm run build
```

CI（`.github/workflows/ci.yml`）会运行后端测试、前端测试与构建，并构建镜像后在断网容器里再跑一遍后端测试。

本地演示环境（假数据，以及假的 NodeSeek/Telegram 响应，**不会触碰真实数据**）见 `backend/dev/README.md`。

架构与可靠性语义见 [docs/architecture.md](docs/architecture.md)；前端与视觉规范见 [docs/frontend.md](docs/frontend.md)；安全说明见 [SECURITY.md](SECURITY.md)。

## 许可证

[MIT](LICENSE)
