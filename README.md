[![ci](https://github.com/3128769/ns-entertainment/actions/workflows/ci.yml/badge.svg)](https://github.com/3128769/ns-entertainment/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

# NodeSeek 娱乐中心

单租户的 NodeSeek 管理程序，自己部署、自己用：

- **每日签到**：固定时间或随机时间区间，随机/固定手气，支持每个账号单独的代理
- **关键词监听**：读取 NodeSeek 的 RSS 新帖，标题命中关键词就发 Telegram
- **私信通知**：新私信即时转发到 Telegram
- **Cookie 掉线提醒**：Cookie 过期时只提醒一次；签到结果不确定时标记“待核实”，**绝不自动重复签到**

> **第一次部署？请看 [安装教程](docs/install.md)**：从一台全新的服务器开始，一步步照着做，包括装 git 和 Docker、怎么打开页面、怎么拿 Cookie 和 Bot Token、常见报错。下面是精简版。

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
| 一台 Linux 服务器 | 需要 **git**、**Docker** 和 **Docker Compose v2**（新装的系统通常都没有，见下面“准备环境”）；两个容器各限 1GB 内存，512MB 以上空闲即可 |
| 出网访问 | `www.nodeseek.com`、`rss.nodeseek.com`、`api.telegram.org`。被 Cloudflare 拦截或直连不通时，可在界面里给账号配置 socks5/http 代理 |
| NodeSeek 账号 Cookie | 见下方“获取 Cookie” |
| Telegram Bot | 见下方“获取 Bot Token 和 Chat ID”（只用签到可不配） |
| 反向代理 + HTTPS（强烈建议） | 登录令牌走明文 HTTP 会被截获。可以用 `deploy/nginx.conf` 作为模板；没有域名时先用 SSH 隧道访问 `127.0.0.1:8090` |

## 准备环境

全新的服务器通常没有 git 和 Docker，先装上。下面以 **Debian / Ubuntu** 为例，以 root 登录执行（非 root 用户请在每条命令前加 `sudo`）：

```bash
apt-get update && apt-get install -y git curl
```

```bash
curl -fsSL https://get.docker.com | sh
```

```bash
docker compose version
```

最后一条能显示版本号就说明 Docker 和 Compose 都装好了。CentOS / Rocky 等系统把第一条换成 `yum install -y git curl`。

> 不想装 git 也可以：`curl -L https://github.com/3128769/ns-entertainment/archive/refs/heads/main.tar.gz | tar xz`，然后进入解压出来的 `ns-entertainment-main` 目录继续下面的步骤。

## 快速开始

```bash
git clone https://github.com/3128769/ns-entertainment.git
cd ns-entertainment

mkdir -p data && chown -R 10001:10001 data && chmod 700 data   # 容器以 UID 10001 运行
docker compose build
docker compose run --rm --no-deps web python -m nsapp.cli migrate   # 建表并生成实例密钥
docker compose up -d

curl http://127.0.0.1:8090/readyz        # 返回 {"status":"ok","ready":true} 即就绪
```

> 第一次 `docker compose build` 要下载基础镜像并安装依赖，需要几分钟；在网络较慢的机器上，到 Docker Hub 拉镜像可能更久，耐心等待即可。

首次启动会创建管理员 `admin`。密码取自环境变量 `NS_ADMIN_PASSWORD`（或 `NS_ADMIN_PASSWORD_FILE` 指向的文件）；都没设置就随机生成，写入 `data/.admin_password`（权限 600，不会打印到日志）：

```bash
cat data/.admin_password
```

然后打开页面登录，按顺序配置：

1. **通知设置** → 添加 Bot（名称、Chat ID、Token），点“检查连接”校验（只校验，不发消息）。
2. **签到账号** → 添加账号，粘贴 Cookie，设置签到时间。
3. 按需在账号里开启 **关键词监听**、**私信通知**、**掉线通知**（每项需要选择 Bot 和接收人 Chat ID）。

### 修改管理员密码

```bash
docker compose run --rm --no-deps web python -m nsapp.cli set-admin-password
```

按提示输入两次新密码（至少 8 位）。修改后该账号所有已登录的会话会立即失效。

### 获取 Cookie

登录 NodeSeek → 浏览器开发者工具（F12）→ Network → 点任意一个发往 `www.nodeseek.com` 的请求 → Request Headers 里的 `Cookie`，复制**整段**。Cookie 会过期，过期后总览页会提示，更新即可。

### 获取 Bot Token 和 Chat ID

1. 在 Telegram 里找 `@BotFather`，发送 `/newbot` 按提示创建，得到 Token（形如 `123456:ABC-DEF…`）。
2. 先给你的 Bot 发一条 `/start`（Bot 无法主动联系没有发过消息的人）。
3. 个人 Chat ID：找 `@userinfobot` 获取；或访问 `https://api.telegram.org/bot<Token>/getUpdates`，在返回里找 `chat.id`。群组的 Chat ID 是负数，需要先把 Bot 拉进群。

## 配置（环境变量）

在 `docker-compose.yml` 的 `environment` 里设置：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `NS_DATA_DIR` | `/data` | 数据目录：SQLite、实例密钥、管理员密码文件 |
| `NS_ADMIN_USER` | `admin` | 管理员用户名（只在首次创建时使用） |
| `NS_ADMIN_PASSWORD` / `NS_ADMIN_PASSWORD_FILE` | 随机生成 | 管理员初始密码，只在首次创建管理员时生效 |
| `NS_SECRET_KEY` | 自动生成到 `data/.secret_key` | 加密 Cookie、代理凭据、Bot Token 的实例密钥。**必须和数据库一起备份**，丢失后无法解密 |
| `NS_SCHEDULER_ENABLED` | worker 为 `1`，web 为 `0` | 是否调度任务。`web` 必须为 `0`，一个实例只能有一个 Worker |
| `NS_JOB_CONCURRENCY` | `4` | Worker 并发，1–16 |
| `NS_WEB_DIR` | 镜像内 `/app/web` | 前端静态文件目录 |

调度固定使用北京时间（Asia/Shanghai），界面上的时间也都是北京时间。

## 备份、升级、回滚

见 [docs/deployment.md](docs/deployment.md)。备份时数据库和 `data/.secret_key` 要一起保存。

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
