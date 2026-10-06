# 安装教程（零基础，每条命令都有解释）

这份教程假设你**从没用过命令行**。每一步都会告诉你：这一步在干什么、命令是什么意思、成功时应该看到什么。

## 先看懂这几个词

| 词 | 白话解释 |
| --- | --- |
| **服务器** | 一台 24 小时开着的远程电脑，程序装在它上面，这样你关了自己的电脑它也能继续签到 |
| **终端** | 一个黑色的窗口，你在里面打字（命令）告诉服务器做什么 |
| **命令** | 一行文字，回车后服务器就照做。下面灰色框里的每一行就是一条命令 |
| **root** | 服务器上权限最大的用户，什么都能做 |
| **git** | 一个下载工具，用来把程序的代码从 GitHub 拿到服务器上 |
| **Docker** | 一个“打包运行”的工具。程序和它需要的所有东西都装在一个“集装箱”（容器）里，不会弄乱你的系统，删除也干净 |
| **镜像 / 容器** | 镜像是“安装包”，容器是“正在运行的程序”。你先做出镜像，再用它启动容器 |
| **端口 8090** | 程序在服务器上的“门牌号”。程序只开在服务器自己内部，**外面不能直接访问**（为了安全） |
| **SSH 隧道** | 在你的电脑和服务器之间搭一条加密的“专用通道”，让你的浏览器能安全地看到服务器内部的页面 |
| **域名 / HTTPS** | 域名是网址（如 `ns.example.com`）；HTTPS 是网址前面的小锁，表示传输加密 |

## 怎么用这份教程

- **灰色框里才是命令**。点框右上角的复制按钮，粘贴到终端，**按回车**。
- **一次只做一条**。等屏幕最后一行又出现 `root@xxx:~#` 这样的提示（说明上一条做完了），再做下一条。
- 输入密码时**屏幕不显示任何字符**，这是正常的，输完直接回车。
- 看不懂的报错，翻到最后的“常见问题”。

整个流程一共 6 步：

```
1 登录服务器 → 2 安装 git 和 Docker → 3 下载程序 → 4 启动 → 5 打开页面 → 6 第一次使用
```

## 0. 你需要准备

| 东西 | 说明 |
| --- | --- |
| 一台 Linux 服务器 | 本教程以 **Debian / Ubuntu** 为例；1 核 1GB 内存以上，能上外网 |
| 服务器的 IP 地址和 root 密码 | 买服务器时厂商会给你 |
| NodeSeek 账号 | 第 6 步要复制它的 Cookie |
| （想收通知才要）Telegram Bot | 第 6 步会教你创建 |
| （可选）一个域名 | 想用 `https://你的域名` 访问才需要；没有也行 |

## 1. 登录服务器

**这一步做什么**：从你的电脑远程连上服务器，之后所有命令都在服务器上执行。

在**你自己电脑**的终端里输入（Mac 打开“终端”，Windows 打开 PowerShell），把 `服务器IP` 换成真实地址：

```bash
ssh root@服务器IP
```

> **这条命令的意思**：`ssh` 是“远程登录”，`root@服务器IP` 是“用 root 用户登录这个地址”。

第一次会问 `Are you sure you want to continue connecting`，输入 `yes` 回车。然后输入密码（不显示字符）回车。

**成功的样子**：最后一行变成 `root@一串名字:~#`。从现在起，**这个窗口里的命令都是在服务器上执行的**。

> 如果你不是 root 用户，下面每条命令前面要加 `sudo `（比如 `sudo apt-get update`）。

## 2. 安装 git 和 Docker

**这一步做什么**：新买的服务器是“空”的，没有下载工具（git）和运行工具（Docker），要先装上。**不装的话，后面会报 `command not found`（找不到这个命令）。**

```bash
apt-get update && apt-get install -y git curl
```

> **这条命令的意思**：`apt-get` 是 Debian/Ubuntu 的“应用商店”。`update` 是刷新软件清单，`install -y git curl` 是安装 git 和 curl（一个下载工具），`-y` 表示“遇到询问都回答是”。中间的 `&&` 表示“前一个成功了才做后一个”。

```bash
curl -fsSL https://get.docker.com | sh
```

> **这条命令的意思**：从 Docker 官方网站下载安装脚本并运行。**要等一两分钟，屏幕会滚动很多字**，耐心等到最后一行出现 `root@...:~#`。

```bash
docker compose version
```

> **这条命令的意思**：问 Docker“你装好了吗？是什么版本？”

**成功的样子**：显示一行类似 `Docker Compose version v2.xx.x` 的字。如果显示 `docker: command not found`，说明上一条没装成功，重新执行上一条，并看一下屏幕里有没有报错。

> CentOS / Rocky 系统：第一条改成 `yum install -y git curl`。

## 3. 下载程序

**这一步做什么**：把程序的代码从 GitHub 拿到服务器上。

```bash
git clone https://github.com/3128769/ns-entertainment.git
```

> **这条命令的意思**：`git clone` 是“把这个网址上的代码完整复制一份下来”。

```bash
cd ns-entertainment
```

> **这条命令的意思**：`cd` 是“进入某个文件夹”。程序下载到了一个叫 `ns-entertainment` 的文件夹里，我们走进去，后面的命令都要在这个文件夹里执行。

**成功的样子**：提示符变成 `root@...:~/ns-entertainment#`（多了 `~/ns-entertainment`，说明你在这个文件夹里）。

> 不想装 git 也行：`curl -L https://github.com/3128769/ns-entertainment/archive/refs/heads/main.tar.gz | tar xz`，然后 `cd ns-entertainment-main`。

## 4. 启动程序

### 4.1 创建数据文件夹

```bash
mkdir -p data && chown -R 10001:10001 data && chmod 700 data
```

> **这条命令的意思**（三小步，用 `&&` 连着）：
> 1. `mkdir -p data`：创建一个叫 `data` 的文件夹，程序的**数据库、密码、加密密钥**都放在这里。
> 2. `chown -R 10001:10001 data`：把这个文件夹的主人改成编号 10001（程序在容器里运行时用的身份），这样程序才有权限写入。
> 3. `chmod 700 data`：只有主人能读写，别人不能看，保护密码和密钥。
>
> **成功的样子**：没有任何输出，直接回到提示符（没消息就是好消息）。

### 4.2 构建（做出“安装包”）

```bash
docker compose build
```

> **这条命令的意思**：按照仓库里的“配方”（`Dockerfile`），下载需要的东西，做出程序的镜像（安装包）。**第一次要几分钟，屏幕可能很久不动，这是正常的，不要关**。
>
> **成功的样子**：最后出现一行 `Built` 或者 `Image ... Built` 之类，然后回到提示符。

### 4.3 初始化数据库

```bash
docker compose run --rm --no-deps web python -m nsapp.cli migrate
```

> **这条命令的意思**：临时运行一下程序里的“初始化工具”，建好数据库的表，并生成**加密密钥**（用来保护你的 Cookie 和 Token）。`--rm` 是“用完就丢”。
>
> **成功的样子**：显示 `{"status": "ok", "version": "3.0.2"}`。

### 4.4 启动

```bash
docker compose up -d
```

> **这条命令的意思**：启动程序。`up` 是“启动”，`-d` 是“在后台运行”，这样你关掉终端它也不会停。
>
> **成功的样子**：显示两行 `Started`（一个是网页和接口 `ns-entertainment`，一个是后台任务 `ns-entertainment-worker`）。

### 4.5 检查有没有准备好

```bash
curl http://127.0.0.1:8090/readyz
```

> **这条命令的意思**：`curl` 是“访问一个网址”。`127.0.0.1` 指“服务器自己”，`8090` 是程序的端口，`readyz` 是“你准备好了吗”。
>
> **成功的样子**：显示 `{"status":"ok","ready":true}`（意思是：状态正常，已经准备好）。
> 如果显示 `503` 或连不上，等 10 秒再来一次。

### 4.6 看管理员密码

```bash
cat data/.admin_password
```

> **这条命令的意思**：`cat` 是“把文件内容显示出来”，这个文件里存着程序自动生成的**管理员密码**。用户名是 `admin`。
>
> **注意**：密码文件末尾没有换行，所以屏幕上密码会和下一行的 `root@...` 连在一起，像这样：
> `这里是密码root@xxx:~/ns-entertainment#`
> **`root@` 开头的是提示符，不是密码的一部分**，密码到 `root@` 前面一个字符为止。注意区分大小写。

## 5. 打开页面

程序只开在服务器**内部**，不能直接用服务器 IP 访问。有两种办法，**没有域名就选 A**。

### A. 没有域名：SSH 隧道（最简单，也最安全）

**这一步做什么**：在你的电脑和服务器之间搭一条加密通道，让你电脑浏览器能看到服务器内部的页面。

在**你自己电脑**的终端（**不是**服务器的那个窗口，新开一个）输入：

```bash
ssh -L 8090:127.0.0.1:8090 root@服务器IP
```

> **这条命令的意思**：登录服务器（和第 1 步一样），同时用 `-L` 把“你电脑的 8090 端口”接到“服务器内部的 8090 端口”。**这个窗口要一直开着**，关了通道就断了。

登录成功后，在你电脑的浏览器地址栏输入：`http://127.0.0.1:8090` 回车。看到登录页，用户名 `admin`，密码是 4.6 里看到的那串。

### B. 有域名：配置 HTTPS（可以随时随地访问）

先把域名的 **A 记录**解析到服务器 IP，并在服务器厂商的控制台放行 **80 和 443** 端口。然后在服务器上依次执行：

```bash
apt-get install -y nginx certbot python3-certbot-nginx
```

> **意思**：安装 nginx（网站“前台”，把外面的访问转给程序）和 certbot（免费申请 HTTPS 证书的工具）。

把下面整段一起复制（把 `你的域名` 换成真实域名）：

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

> **意思**：写一个配置文件，告诉 nginx“把访问这个域名的人，转给内部的 8090 端口”。`X-Real-IP` 那行不能删：程序靠它给“输错密码”限速。

```bash
nginx -t && systemctl reload nginx
```

> **意思**：先检查配置有没有写错（`-t`），没错就让 nginx 重新加载。

```bash
certbot --nginx -d 你的域名
```

> **意思**：自动申请免费 HTTPS 证书并配置好。按提示填邮箱、同意条款，问“是否把 HTTP 跳转到 HTTPS”选**跳转**。证书会自动续期。

完成后浏览器打开 `https://你的域名` 即可。

## 6. 第一次使用

登录后，**强烈建议先改掉管理员密码**（4.6 里的密码是自动生成的，可能出现在你的截图里）。在服务器上执行：

```bash
docker compose run --rm --no-deps web python -m nsapp.cli set-admin-password
```

> **意思**：改管理员密码。按提示输入两次新密码（至少 8 位，输入时不显示）。改完后所有已登录的页面会被要求重新登录。

然后在页面里依次做：

1. **通知设置** → 添加 Bot → 点“检查连接”。（只想自动签到、不要通知，可以跳过）
2. **签到账号** → 添加账号 → 粘贴 Cookie → 设置签到时间。
3. 需要的话，在账号里开启 **关键词监听**、**私信通知**、**掉线通知**。

**怎么拿 Cookie**（Cookie 相当于“你已登录 NodeSeek 的凭证”）：登录 NodeSeek → 按 F12 打开开发者工具 → 点 Network（网络）→ 刷新页面 → 点任意一个发往 `www.nodeseek.com` 的请求 → 在 Request Headers（请求头）里找到 `Cookie`，复制**整段**。

**怎么拿 Bot Token 和 Chat ID**（Bot 是用来给你发 Telegram 通知的机器人）：

1. 在 Telegram 里找 `@BotFather`，发送 `/newbot`，按提示起名，得到 **Token**（形如 `123456:ABC-DEF…`）。
2. **先给你刚创建的 Bot 发一条 `/start`**（Bot 不能主动联系没跟它说过话的人）。
3. **Chat ID**（通知发给谁）：在 Telegram 找 `@userinfobot`，它会告诉你你的 ID（一串数字）。想发到群里，要先把 Bot 拉进群，群的 ID 是负数。

## 7. 日常维护（每条命令是干嘛的）

先进入程序文件夹（新开终端登录服务器后要先做这一步）：

```bash
cd ~/ns-entertainment
```

| 想做的事 | 命令 | 意思 |
| --- | --- | --- |
| 看程序有没有在运行 | `docker compose ps` | 列出两个容器的状态，看到 `running` / `healthy` 就是正常 |
| 看后台任务日志 | `docker compose logs --tail 50 worker` | 显示后台任务最近 50 行日志，排查问题用 |
| 重启程序 | `docker compose restart` | 重启两个容器，数据不会丢 |
| 停止程序 | `docker compose down` | 停止并移除容器。**`data/` 文件夹里的数据都还在** |
| 再次启动 | `docker compose up -d` | 同 4.4 |
| 更新到新版本 | 见下面 | |

**更新到新版本**（建议先备份）。依次执行：

```bash
git pull
```

> **意思**：从 GitHub 拉取最新的代码。

```bash
docker compose build && docker compose run --rm --no-deps web python -m nsapp.cli migrate && docker compose up -d
```

> **意思**：重新做镜像 → 升级数据库（没有变化就什么也不做）→ 用新版本重新启动。

**备份**（把数据库和密钥打包存一份。**数据库和密钥必须一起备份**，丢了密钥就解不开 Cookie 和 Token；备份文件要复制一份到服务器之外）：

```bash
docker compose stop worker web
```

> **意思**：先停下来，保证备份时数据不会变。

```bash
docker compose run --rm --no-deps --user 0 --entrypoint python web scripts/backup.py /data/backups/我的备份
```

> **意思**：运行备份工具，把备份存到 `data/backups/我的备份/`。成功会显示 `"status": "ok"`。

```bash
docker compose up -d
```

> **意思**：备份完，重新启动。

## 8. 常见问题

| 你看到的 | 是什么意思 / 怎么办 |
| --- | --- |
| `git: command not found` | 没装 git，回到第 2 步执行第一条命令 |
| `docker: command not found` | 没装 Docker，回到第 2 步执行第二条命令，再用 `docker compose version` 确认 |
| `permission denied`（没权限） | 你不是 root 用户，命令前面加 `sudo ` |
| `No such file or directory` | 你不在程序文件夹里，先 `cd ~/ns-entertainment`；或者你在**自己电脑**上输入了本该在服务器上输入的命令 |
| `docker compose build` 很久不动 | 第一次要下载东西，网络慢时可能十几分钟，耐心等，不要关窗口 |
| `readyz` 返回 503 或连不上 | 刚启动，等 10 秒再试；还不行就看日志：`docker compose logs --tail 50 worker` |
| 页面左下角显示“后台服务未运行” | 后台任务没起来：`docker compose ps` 看状态，再看上一条的日志 |
| 浏览器打不开 | 没有域名时要先建好 SSH 隧道（5.A）并保持窗口开着；有域名时检查 80/443 端口是否放行、域名是否解析到本机 |
| 登录说“用户名或密码错误” | 密码要区分大小写，并且**不要把 `root@` 开头的提示符当成密码的一部分**；忘了就用 6 里的改密码命令 |
| 连续输错后提示“尝试次数过多” | 等 5 分钟再试 |
| 状态显示“访问受阻” | NodeSeek 的防护拦截了服务器 IP：在“代理管理”添加代理，再到账号里选用 |
| 签到显示“待核实” | 请求可能已经成功了：先到 NodeSeek 看一下是否已签到，系统不会自动重签 |
| Cookie 过期 | 重新登录 NodeSeek 复制新的 Cookie，在账号里更新 |

更多部署、升级和回滚细节见 [deployment.md](deployment.md)。
