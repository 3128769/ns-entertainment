# 安装教程（从一台新服务器开始）

照着一步步做，不需要懂 Docker。全程在服务器的终端里输入命令。每一步的命令都是**单独一条**，复制一条、回车、看结果，再复制下一条。

## 0. 你需要准备

| 东西 | 说明 |
| --- | --- |
| 一台 Linux 服务器 | 本教程以 **Debian / Ubuntu** 为例，1 核 1GB 内存以上，能访问外网 |
| 服务器的 IP 和 root 密码 | 用来登录 |
| NodeSeek 账号 | 登录后要复制 Cookie，见第 6 步 |
| （可选）一个 Telegram Bot | 要收通知才需要，见第 6 步 |
| （可选）一个域名 | 想用 `https://你的域名` 访问才需要；没有域名也能用，见第 5 步 A |

## 1. 登录服务器

在你自己电脑的终端（Mac 用“终端”，Windows 用 PowerShell）输入，把 `服务器IP` 换成真实地址：

```bash
ssh root@服务器IP
```

输入密码（输入时屏幕不显示字符，这是正常的），看到 `root@xxx:~#` 就登录成功了。以下所有命令都在这个窗口里执行。

> 如果你不是 root 用户，下面每条命令前面加上 `sudo `。

## 2. 安装 git 和 Docker

新装的系统通常**两样都没有**，直接运行会报 `command not found`。

```bash
apt-get update && apt-get install -y git curl
```

```bash
curl -fsSL https://get.docker.com | sh
```

安装 Docker 要一两分钟，屏幕会滚动很多字，等它结束。然后检查：

```bash
docker compose version
```

显示一行版本号（例如 `Docker Compose version v2.x.x`）就对了。如果提示 `docker: command not found`，说明上一条没有成功，重新执行上一条，并留意屏幕里的报错。

> CentOS / Rocky：第一条换成 `yum install -y git curl`。

## 3. 下载程序

```bash
git clone https://github.com/3128769/ns-entertainment.git
```

```bash
cd ns-entertainment
```

> 不想装 git：`curl -L https://github.com/3128769/ns-entertainment/archive/refs/heads/main.tar.gz | tar xz`，再 `cd ns-entertainment-main`。

## 4. 启动

创建数据目录（程序的数据库和密钥都放在这里，**要备份**）：

```bash
mkdir -p data && chown -R 10001:10001 data && chmod 700 data
```

构建镜像。**第一次需要几分钟**，会下载基础镜像和依赖，屏幕长时间不动是正常的：

```bash
docker compose build
```

初始化数据库：

```bash
docker compose run --rm --no-deps web python -m nsapp.cli migrate
```

启动：

```bash
docker compose up -d
```

检查是否就绪：

```bash
curl http://127.0.0.1:8090/readyz
```

返回 `{"status":"ok","ready":true}` 就启动成功了。如果返回 `503` 或连不上，等十秒再试一次；仍然不行，见最后的“常见问题”。

查看自动生成的管理员密码（用户名是 `admin`）：

```bash
cat data/.admin_password
```

## 5. 打开页面

程序只监听服务器本机的 `8090` 端口，**不会直接暴露到公网**（这是为了安全，登录信息不该走明文）。有两种方式访问：

### A. 没有域名：用 SSH 隧道（最简单，也最安全）

在**你自己电脑**的终端（不是服务器）输入，这个窗口要保持打开：

```bash
ssh -L 8090:127.0.0.1:8090 root@服务器IP
```

然后在你电脑的浏览器打开 `http://127.0.0.1:8090`，用 `admin` 和上一步的密码登录。

### B. 有域名：配置 HTTPS（可以随时随地访问）

先把域名的 **A 记录**解析到服务器 IP，并在服务器厂商的控制台放行 **80 和 443** 端口。然后在服务器上：

```bash
apt-get install -y nginx certbot python3-certbot-nginx
```

创建 nginx 配置（把 `你的域名` 换成真实域名，整段一起复制）：

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
```

申请免费 HTTPS 证书（按提示填邮箱、同意条款，问到是否跳转 HTTPS 选“跳转”）：

```bash
certbot --nginx -d 你的域名
```

完成后浏览器打开 `https://你的域名` 即可。证书会自动续期。

> `X-Real-IP` 那一行不能删：程序靠它给“输错密码”限速。

## 6. 第一次使用

登录后依次做：

1. **通知设置** → 添加 Bot → 点“检查连接”。（只签到、不要通知可以跳过）
2. **签到账号** → 添加账号 → 粘贴 Cookie → 设置签到时间。
3. 需要的话，在账号里开启 **关键词监听**、**私信通知**、**掉线通知**。

**怎么拿 Cookie**：登录 NodeSeek → 按 F12 打开开发者工具 → Network（网络）→ 点任意一个发往 `www.nodeseek.com` 的请求 → 在 Request Headers（请求头）里找到 `Cookie`，复制**整段**。

**怎么拿 Bot Token 和 Chat ID**：

1. 在 Telegram 里找 `@BotFather`，发送 `/newbot`，按提示创建，得到 Token（形如 `123456:ABC-DEF…`）。
2. **先给你的 Bot 发一条 `/start`**（Bot 不能主动联系没发过消息的人）。
3. 个人 Chat ID：找 `@userinfobot` 获取，或访问 `https://api.telegram.org/bot你的Token/getUpdates`，在返回里找 `chat.id`。群组的 Chat ID 是负数，要先把 Bot 拉进群。

## 7. 日常维护

**更新到新版本**（先备份，见下）：

```bash
cd ~/ns-entertainment && git pull
```

```bash
docker compose build && docker compose run --rm --no-deps web python -m nsapp.cli migrate && docker compose up -d
```

**备份**（数据库和密钥必须一起备份，丢了密钥就解不开 Cookie 和 Token；把备份复制一份到服务器之外）：

```bash
docker compose stop worker web
```

```bash
docker compose run --rm --no-deps --user 0 --entrypoint python web scripts/backup.py /data/backups/我的备份
```

```bash
docker compose up -d
```

备份会出现在 `data/backups/我的备份/`。

**修改管理员密码**：

```bash
docker compose run --rm --no-deps web python -m nsapp.cli set-admin-password
```

**看日志 / 重启 / 停止**：

```bash
docker compose logs --tail 50 worker
```

```bash
docker compose restart
```

```bash
docker compose down
```

`docker compose down` 只停止程序，`data/` 里的数据都还在。

## 8. 常见问题

| 现象 | 原因和办法 |
| --- | --- |
| `git: command not found` | 没装 git，执行第 2 步第一条 |
| `docker: command not found` | 没装 Docker，执行第 2 步第二条，再用 `docker compose version` 确认 |
| `permission denied` | 不是 root 用户：命令前加 `sudo ` |
| `docker compose build` 很久不动 | 第一次要下载镜像，网络慢时可能十几分钟，耐心等；确认服务器能访问外网 |
| `readyz` 返回 503 | 刚启动，等 10 秒再试；仍然不行看日志：`docker compose logs --tail 50 worker` |
| 页面右下角/侧栏显示“后台服务未运行” | Worker 没起来：`docker compose ps` 看状态，再看上一条的日志 |
| 浏览器打不开 | 没有域名时要先建立 SSH 隧道（第 5 步 A）；有域名时检查 80/443 端口是否放行、域名是否解析到本机 |
| 忘记管理员密码 | 执行“修改管理员密码”那条命令 |
| 状态显示“访问受阻” | NodeSeek 的 Cloudflare 拦截了服务器 IP：在“代理管理”添加代理，再到账号里选用 |
| 签到显示“待核实” | 请求可能已成功：先到 NodeSeek 确认，系统不会自动重签 |
| Cookie 过期 | 重新登录 NodeSeek 复制新 Cookie，在账号里更新 |

更多部署、升级和回滚细节见 [deployment.md](deployment.md)。
