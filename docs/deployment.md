# 部署、升级与回滚

镜像由 `Dockerfile` 多阶段构建：Node 只用于构建前端，运行时只有 Python。到 Docker Hub 拉取基础镜像很慢时，可以用主机上已有的镜像：`--build-arg NODE_IMAGE=... --build-arg PYTHON_IMAGE=...`（经典构建器 `DOCKER_BUILDKIT=0` 会直接使用本地镜像）。`docker compose` 启动 `web` 与 `worker` 两个服务；反向代理（见 `deploy/nginx.conf`）只指向 `127.0.0.1:8090`。API 只监听本机回环地址，登录限速使用 nginx 写入的 `X-Real-IP`。

## 新安装

从零开始的逐条教程见 [README](../README.md#安装教程每一条命令的解释)。命令摘要：

```bash
mkdir -p data && sudo chown -R 10001:10001 data && chmod 700 data
docker compose build
docker compose run --rm --no-deps web python -m nsapp.cli migrate   # 建表并生成实例密钥
docker compose run --rm --no-deps web python -m nsapp.cli set-admin-password   # 自己设置管理员密码（可选）
docker compose up -d
curl --fail http://127.0.0.1:8090/readyz
```

不执行 `set-admin-password` 时，首次启动会创建管理员；密码取自 `NS_ADMIN_PASSWORD` / `NS_ADMIN_PASSWORD_FILE`，都没有则随机生成并写入 `data/.admin_password`（权限 600，不会打印到日志）。

## 从 2.0.x 升级到 3.x

数据库结构没有变化（迁移仍是 `0001`），因此升级和回滚都不需要迁移数据。

1. **构建并测试候选镜像**（不影响线上）：
   ```bash
   docker build -t ns-entertainment:3.0.2 .
   docker build --target test -t ns-entertainment:3.0.2-test . && docker run --rm --network none ns-entertainment:3.0.2-test
   ```
2. **用生产数据的副本演练**：用 SQLite 在线备份复制 `app.sqlite` 和 `.secret_key` 到临时目录，`NS_SCHEDULER_ENABLED=0`，只读检查接口返回与数据库一致。
3. **停写、备份**：
   ```bash
   docker compose stop web worker
   docker compose run --rm --no-deps --user 0 --entrypoint python web scripts/backup.py /data/backups/release-$(date -u +%Y%m%d-%H%M%S)
   ```
   同时保留旧源码、旧 compose 和旧镜像标签（`ns-entertainment:2.0.2`）。
4. 换入新代码与 compose，`docker compose up -d`，检查 `healthz`、`readyz`、`docker compose logs worker`，确认出现 `worker_started` 且任务正常执行。

## 回滚到 2.0.2

两个版本使用同一份数据库结构，可以直接换回旧镜像和旧 compose，**保留**当前数据库：

```bash
docker compose down
# 恢复升级前保存的源码和 compose（备份目录里的 source-before.tgz）
tar -xzf <备份目录>/source-before.tgz -C <部署目录>
docker compose up -d --no-build
```

仅当数据本身出了问题才用 `scripts/restore.py` 恢复备份；恢复会丢失备份之后的运行结果和通知账本，并可能导致已发送的通知被再次触发。恢复前先停掉 `web` 与 `worker`。

## 备份与恢复

`scripts/backup.py <目录>` 用 SQLite 在线备份 API 生成一致性副本，并复制 `.secret_key` 与 `.admin_password`（权限 600）。**数据库和密钥必须一起保存**，没有密钥无法解密 Cookie 和 Token。`scripts/restore.py <备份目录>` 先校验完整性，再把被替换的文件挪到 `backups/restore-displaced-*`。

## 故障排查

- `healthz` 失败：看 `docker compose ps` 和 web 日志。
- `readyz` 503：迁移未完成，或 Worker 心跳过期（界面左下角会显示“后台服务未运行”）。
- `uncertain`（待核实）：签到或 Telegram 请求可能已成功。先人工到 NodeSeek / Telegram 核对，再决定是否手动重试；系统不会自动重发。
- 队列状态：登录后访问 `/api/system/tasks`。
- 日志只含 ID、状态码、耗时和错误码，不含 Cookie/Token/通知正文。

## 日常维护

先登录服务器，再进入程序文件夹：`cd ~/ns-entertainment`。

| 想做的事 | 命令 |
| --- | --- |
| 看程序有没有在运行 | `docker compose ps`（`running` / `healthy` 就是正常） |
| 看后台日志 | `docker compose logs --tail 50 worker` |
| 重启（数据不会丢） | `docker compose restart` |
| 停止（`data/` 里的数据还在） | `docker compose down` |
| 再次启动 | `docker compose up -d` |
| 改管理员密码 / 忘记密码 | `docker compose run --rm --no-deps web python -m nsapp.cli set-admin-password` |

**更新到新版本**（建议先备份）：

```bash
git pull
docker compose build && docker compose run --rm --no-deps web python -m nsapp.cli migrate && docker compose up -d
```

先拉取最新代码，再重新构建、升级数据库（没有变化就什么也不做）、用新版本重新启动。数据和密码都不会丢。

**手动备份**：

```bash
docker compose stop worker web
docker compose run --rm --no-deps --user 0 --entrypoint python web scripts/backup.py /data/backups/我的备份
docker compose up -d
```

备份出现在 `data/backups/我的备份/`，成功会显示 `"status": "ok"`。数据库和密钥必须一起保存，并复制一份到服务器之外。

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

## 用域名访问（HTTPS）

不想每次都开 SSH 隧道，可以用域名访问。先把域名的 A 记录解析到服务器 IP，并放行 80 和 443 端口，然后在服务器上依次执行：

```bash
apt-get install -y nginx certbot python3-certbot-nginx
```

安装 nginx（把外面的访问转给程序）和 certbot（免费申请 HTTPS 证书）。

下面整段一起复制（把 `你的域名` 换成真实域名）：

```bash
cat > /etc/nginx/conf.d/ns.conf <<'EOF'
server {
    listen 80;
    server_name 你的域名;
    client_max_body_size 25m;

    location / {
        proxy_pass http://127.0.0.1:8090;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 180s;
    }
}
EOF
```

```bash
nginx -t && systemctl reload nginx
certbot --nginx -d 你的域名
```

先检查 nginx 配置，再让它重新加载；然后 certbot 自动申请证书（按提示填邮箱、同意条款，问是否跳转到 HTTPS 选“跳转”，证书会自动续期）。完成后用 `https://你的域名` 访问。

`X-Real-IP` 那行不能删：程序靠它给“输错密码”限速。`deploy/nginx.conf` 是证书申请完成之后的完整模板（含安全响应头），可以对照参考。

## 常见问题

| 你看到的 | 是什么意思 / 怎么办 |
| --- | --- |
| `git: command not found` / `docker: command not found` | 没装 git 或 Docker，回到 README 的第 2 步 |
| `permission denied` | 你不是 root 用户，命令前面加 `sudo ` |
| `No such file or directory` | 不在程序文件夹里（先 `cd ~/ns-entertainment`），或者把本该在服务器上输入的命令输到了自己电脑上 |
| `docker compose build` 很久不动 | 第一次要下载东西，网络慢时可能十几分钟，不要关窗口 |
| 登录提示“用户名或密码错误” | 用户名是 `admin`；密码区分大小写；`cat data/.admin_password` 的输出里 `root@` 开头的是提示符，不属于密码；忘了就重新设置 |
| 提示“尝试次数过多” | 输错太多次，等 5 分钟再试 |
| 页面显示“后台服务未运行” | `docker compose ps` 看状态，再看 worker 日志 |
| 状态显示“访问受阻” | NodeSeek 的防护拦截了服务器 IP：在“代理管理”添加代理，再到账号里选用 |
| 签到显示“待核实” | 请求可能已经成功：先到 NodeSeek 确认，系统不会自动重签 |

## 开发

```bash
# 后端
cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q

# 前端
cd frontend && npm ci && npm test && npm run build
```

CI（`.github/workflows/ci.yml`）会运行后端测试、前端测试与构建，并构建镜像后在断网容器里再跑一遍后端测试。本地演示环境（假数据和假的 NodeSeek/Telegram 响应，不会触碰真实数据）见 `backend/dev/README.md`。

架构与可靠性语义见 [architecture.md](architecture.md)；前端与视觉规范见 [frontend.md](frontend.md)；安全说明见 [../SECURITY.md](../SECURITY.md)。
