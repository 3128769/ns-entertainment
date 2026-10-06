#!/usr/bin/env bash
# NodeSeek 娱乐中心 · 安装 / 更新 / 卸载
#
#   bash install.sh                       安装（只会问：域名（可选）、管理员密码）
#   bash install.sh --update              更新到最新版（先自动备份数据）
#   bash install.sh --set-password        重新设置管理员密码
#   bash install.sh --set-domain 域名     以后再绑定域名，并自动配置 HTTPS
#   bash install.sh --uninstall           卸载（删除程序、配置和全部数据）
#
# 适用：全新的 Debian / Ubuntu 服务器（x86_64 或 ARM64），用 root 运行。
# 不绑定域名时，直接用 http://服务器IP 访问（不加密）；绑定域名会自动申请免费的 HTTPS 证书。
# 可选的环境变量（想免交互，或有特殊需求时用）：
#   NS_DOMAIN=ns.example.com   域名（可选）。不设置则交互输入，直接回车 = 不绑定域名，用 IP 访问
#   NS_ADMIN_PASSWORD=...      管理员密码（至少 8 位）。不设置则交互输入，回车自动生成
#   NS_EMAIL=me@example.com    申请 HTTPS 证书用的邮箱（可选，用于到期提醒）
#   NS_SKIP_NGINX=1            不装 nginx 和证书，程序只监听 127.0.0.1:端口（已有自己的反向代理时用）
#   NS_PORT=8090               程序在本机监听的端口
#   NS_DIR=/opt/ns-entertainment   安装目录
set -Eeuo pipefail

REPO_RAW="${NS_REPO_RAW:-https://raw.githubusercontent.com/3128769/ns-entertainment/main}"
DIR="${NS_DIR:-/opt/ns-entertainment}"
PORT="${NS_PORT:-8090}"
SKIP_NGINX="${NS_SKIP_NGINX:-0}"
NGINX_CONF="/etc/nginx/conf.d/ns-entertainment.conf"
IMAGE="ghcr.io/3128769/ns-entertainment:latest"

DOMAIN=""
PASSWORD=""
GENERATED=0
HTTPS=0

if [ -t 1 ]; then C_OK=$'\033[1;32m'; C_WARN=$'\033[1;33m'; C_ERR=$'\033[1;31m'; C_OFF=$'\033[0m'; else C_OK=""; C_WARN=""; C_ERR=""; C_OFF=""; fi
say()  { printf '%s==>%s %s\n' "$C_OK" "$C_OFF" "$*"; }
warn() { printf '%s!!%s %s\n' "$C_WARN" "$C_OFF" "$*" >&2; }
die()  { printf '%s错误：%s%s\n' "$C_ERR" "$C_OFF" "$*" >&2; exit 1; }
trap 'warn "第 $LINENO 行出错了，上面的最后几行是原因。修复后可以重新运行本脚本。"' ERR

usage() {
  cat <<'EOF'
用法：bash install.sh [选项]
  （无选项）            安装
  --update              更新到最新版（先自动备份数据）
  --set-password        重新设置管理员密码
  --set-domain 域名     绑定域名并自动配置 HTTPS（安装时没填域名，以后想加密就用这个）
  --uninstall           卸载（删除程序、配置和全部数据，需要输入确认）
  -h, --help            显示本说明
EOF
}

# ---------- 小工具 ----------

have_tty() { [ -r /dev/tty ] && [ -w /dev/tty ] && (: </dev/tty) 2>/dev/null; }

# ask 变量名 提示 —— 读一行（从终端读，所以 curl | bash 也能用）；没有终端时变量为空
# 内部变量用 __reply：调用方传进来的变量名（如 answer）不能和它重名，否则会被局部变量遮住
ask() {
  local __reply=""
  if have_tty; then read -r -p "$2" __reply </dev/tty || true; fi
  printf -v "$1" '%s' "$__reply"
}
ask_secret() {
  local __reply=""
  if have_tty; then read -r -s -p "$2" __reply </dev/tty || true; printf '\n' >&2; fi
  printf -v "$1" '%s' "$__reply"
}

# 在安装目录里运行 docker compose；</dev/null 防止它吞掉脚本的标准输入
dc() { (cd "$DIR" && docker compose "$@" </dev/null); }

get_conf() { sed -n "s/^$1=//p" "$DIR/.install" 2>/dev/null | head -n 1; }

valid_domain() { [[ "$1" =~ ^([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,}$ ]]; }

public_ip() {
  local url ip
  for url in https://api.ipify.org https://ipv4.icanhazip.com https://ifconfig.me; do
    ip="$(curl -4 -fsS -m 6 "$url" 2>/dev/null | tr -d '[:space:]' || true)"
    if [[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then printf '%s' "$ip"; return 0; fi
  done
  return 1
}

gen_password() { { LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 20; } || true; }

# render_nginx 域名 端口 —— 域名为空时作为默认站点，用 IP 访问
render_nginx() {
  local listen="80" name="$1"
  if [ -z "$1" ]; then listen="80 default_server"; name="_"; fi
  sed -e "s/__LISTEN__/$listen/g" -e "s/__NAME__/$name/g" -e "s/__PORT__/$2/g" <<'EOF'
server {
    listen __LISTEN__;
    server_name __NAME__;
    client_max_body_size 25m;

    location / {
        proxy_pass http://127.0.0.1:__PORT__;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 180s;
    }
}
EOF
}

# ---------- 检查 ----------

check_basics() {
  [ "$(id -u)" = 0 ] || die "请用 root 运行：先执行 sudo -i 切换成 root，再运行本脚本。"
  command -v apt-get >/dev/null 2>&1 || die "本脚本只支持 Debian / Ubuntu。其他系统请看 README 里的「手动部署」。"
  case "$(uname -m)" in x86_64|aarch64) ;; *) die "不支持的 CPU 架构：$(uname -m)（需要 x86_64 或 ARM64）。" ;; esac
  if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then die "NS_PORT 不是有效的端口：$PORT"; fi
  if [[ "$DIR" != /* ]] || [ "$DIR" = / ]; then die "NS_DIR 必须是绝对路径，且不能是 /：$DIR"; fi
}

require_installed() { [ -f "$DIR/.install" ] || die "没有找到安装（$DIR）。请先运行：bash install.sh"; }

check_port80() {
  local owner
  owner="$(ss -ltnpH 'sport = :80' 2>/dev/null | grep -v '"nginx"' || true)"
  [ -z "$owner" ] || die "80 端口已被其他程序占用：
$owner
请先停掉它；或者设置 NS_SKIP_NGINX=1，用你自己的反向代理。"
}

# ---------- 交互 ----------

# 域名可以为空：不绑定域名，用 IP 访问
choose_domain() {
  if [ "$SKIP_NGINX" = 1 ]; then DOMAIN=""; return 0; fi
  DOMAIN="${NS_DOMAIN:-}"
  if [ -z "$DOMAIN" ] && have_tty; then
    printf '域名是可选的：绑定域名可以自动配置 HTTPS 加密；不绑定就直接回车，用服务器 IP 访问（http，不加密）。\n' >&2
    ask DOMAIN "域名（可选）: "
  fi
  if [ -z "$DOMAIN" ]; then return 0; fi
  DOMAIN="$(printf '%s' "$DOMAIN" | tr '[:upper:]' '[:lower:]')"
  valid_domain "$DOMAIN" || die "域名格式不对：$DOMAIN"

  local ip resolved ans=""
  ip="$(public_ip || true)"
  resolved="$(getent ahostsv4 "$DOMAIN" 2>/dev/null | awk 'NR==1{print $1}' || true)"
  if [ -n "$ip" ] && [ "$resolved" != "$ip" ]; then
    warn "域名 $DOMAIN 现在解析到「${resolved:-无}」，本机公网 IP 是 $ip。"
    warn "解析还没生效或没有指向本机时，HTTPS 证书会申请失败。"
    have_tty || die "请先把域名解析到 $ip，再重新运行。"
    ask ans "仍然继续吗？[y/N] "
    [[ "$ans" =~ ^[Yy]$ ]] || die "已取消。请先把域名解析到 $ip，再重新运行。"
  fi
}

choose_password() {
  PASSWORD="${NS_ADMIN_PASSWORD:-}"; GENERATED=0
  if [ -z "$PASSWORD" ] && have_tty; then
    local again=""
    printf '请设置管理员密码（用户名固定是 admin，至少 8 位；直接回车 = 自动生成）。\n' >&2
    ask_secret PASSWORD "管理员密码: "
    if [ -n "$PASSWORD" ]; then
      ask_secret again "再输入一次: "
      [ "$PASSWORD" = "$again" ] || die "两次输入不一致，已取消。"
    fi
  fi
  if [ -z "$PASSWORD" ]; then PASSWORD="$(gen_password)"; GENERATED=1; fi
  [ "${#PASSWORD}" -ge 8 ] || die "管理员密码至少 8 位。"
}

# ---------- 安装步骤 ----------

install_packages() {
  export DEBIAN_FRONTEND=noninteractive
  local missing=()
  dpkg -s curl ca-certificates >/dev/null 2>&1 || missing+=(curl ca-certificates)
  if [ "$SKIP_NGINX" != 1 ]; then dpkg -s nginx certbot python3-certbot-nginx >/dev/null 2>&1 || missing+=(nginx certbot python3-certbot-nginx); fi
  if [ "${#missing[@]}" -gt 0 ]; then
    say "安装依赖：${missing[*]}"
    apt-get update -y
    apt-get install -y "${missing[@]}"
  fi
  if ! command -v docker >/dev/null 2>&1; then
    say "安装 Docker（官方脚本，需要一两分钟）…"
    curl -fsSL https://get.docker.com | sh
  fi
  systemctl enable --now docker >/dev/null 2>&1 || true
  docker compose version >/dev/null 2>&1 || die "没有找到 Docker Compose v2。请按官方文档安装 docker-compose-plugin：https://docs.docker.com/compose/install/linux/"
}

prepare_dir() {
  mkdir -p "$DIR"
  local tmp; tmp="$(mktemp)"
  curl -fsSL "$REPO_RAW/docker-compose.template.yml" -o "$tmp" || { rm -f "$tmp"; die "下载配置文件失败：$REPO_RAW/docker-compose.template.yml"; }
  grep -q 'ns-data' "$tmp" || { rm -f "$tmp"; die "下载到的配置文件内容不对。"; }
  install -m 644 "$tmp" "$DIR/docker-compose.yml"; rm -f "$tmp"
  printf 'NS_PORT=%s\n' "$PORT" > "$DIR/.env"; chmod 600 "$DIR/.env"
}

set_admin_password() {
  NS_NEW_PASSWORD="$PASSWORD" dc run --rm --no-deps -T -e NS_NEW_PASSWORD web python -m nsapp.cli set-admin-password >/dev/null
}

start_app() {
  say "下载程序镜像（ghcr.io）…"
  dc pull
  say "初始化数据库…"
  dc run --rm --no-deps -T migrate >/dev/null
  say "设置管理员密码…"
  set_admin_password
  say "启动程序…"
  dc up -d --wait --wait-timeout 180
  curl -fsS -m 10 "http://127.0.0.1:$PORT/readyz" >/dev/null || die "程序没有就绪。看日志：cd $DIR && docker compose logs --tail 50"
}

open_firewall() {
  if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q '^Status: active'; then
    say "放行防火墙（ufw）的 80 端口…"
    ufw allow 80/tcp >/dev/null
    if [ -n "$DOMAIN" ]; then ufw allow 443/tcp >/dev/null; fi
  fi
}

# nginx 自带的欢迎页站点会占用默认站点；只在它确实是原装、没有托管任何内容时才停用（只删软链接）
disable_stock_default_site() {
  local f=/etc/nginx/sites-enabled/default body
  [ -L "$f" ] || return 0
  [ "$(readlink -f "$f")" = /etc/nginx/sites-available/default ] || return 0
  body="$(grep -vE '^[[:space:]]*#' "$f" || true)"   # 原装配置的注释里有 fastcgi_pass 示例，所以先去掉注释再判断
  if [[ "$body" =~ (proxy_pass|fastcgi_pass|uwsgi_pass) ]]; then return 0; fi
  say "停用 nginx 自带的欢迎页站点（它会占用默认站点）…"
  rm -f "$f"
}

setup_nginx() {
  if [ "$SKIP_NGINX" = 1 ]; then return 0; fi
  say "配置 nginx…"
  if [ -z "$DOMAIN" ]; then disable_stock_default_site; fi
  render_nginx "$DOMAIN" "$PORT" > "$NGINX_CONF"
  if ! nginx -t >/dev/null 2>&1; then
    nginx -t || true
    rm -f "$NGINX_CONF"
    die "nginx 配置检查没通过，已撤销。可能是 nginx 里已有别的默认站点；可以设置 NS_SKIP_NGINX=1，用你自己的反向代理。"
  fi
  systemctl enable --now nginx >/dev/null 2>&1 || true
  systemctl reload nginx
  open_firewall

  HTTPS=0
  if [ -z "$DOMAIN" ]; then return 0; fi
  say "申请 HTTPS 证书（Let's Encrypt，免费，自动续期；视为同意其服务条款）…"
  local args=(--nginx -d "$DOMAIN" --non-interactive --agree-tos --redirect)
  if [ -n "${NS_EMAIL:-}" ]; then args+=(-m "$NS_EMAIL"); else args+=(--register-unsafely-without-email); fi
  if certbot "${args[@]}" </dev/null; then
    HTTPS=1
  else
    warn "证书申请失败，网站暂时只能用 http 访问（不加密，请先不要输入重要信息）。"
    warn "多半是域名没有解析到本机，或云服务器的防火墙/安全组没有放行 80 和 443。修好后执行："
    warn "  bash install.sh --set-domain $DOMAIN"
  fi
}

save_state() {
  {
    printf 'DOMAIN=%s\n' "$DOMAIN"
    printf 'PORT=%s\n' "$PORT"
    printf 'NGINX=%s\n' "$([ "$SKIP_NGINX" = 1 ] && echo 0 || echo 1)"
    printf 'HTTPS=%s\n' "$HTTPS"
  } > "$DIR/.install"
}

show_address() {
  local ip
  if [ "$SKIP_NGINX" = 1 ]; then
    printf '    程序只监听 http://127.0.0.1:%s ，请自己配置反向代理（强烈建议 HTTPS）。\n' "$PORT"
  elif [ "$HTTPS" = 1 ]; then
    printf '    访问地址：https://%s\n' "$DOMAIN"
  elif [ -n "$DOMAIN" ]; then
    printf '    访问地址：http://%s （证书申请失败，暂时未加密）\n' "$DOMAIN"
  else
    ip="$(public_ip || true)"
    printf '    访问地址：http://%s\n' "${ip:-你的服务器IP}"
    printf '    注意：现在是 http 明文访问，密码和 Cookie 在网络上不加密。想加密，绑定一个域名即可：\n'
    printf '          bash install.sh --set-domain 你的域名      （没有域名可以用免费的 ns.IP地址用短横线连接.sslip.io，例如 ns.203-0-113-10.sslip.io）\n'
  fi
}

show_credentials() {
  printf '    用户名：admin\n'
  if [ "$GENERATED" = 1 ]; then
    printf '    密码：  %s\n' "$PASSWORD"
    printf '    （自动生成的密码只显示这一次，请立刻保存。忘记了可以执行 bash install.sh --set-password 重设）\n'
  else
    printf '    密码：  你刚才设置的密码\n'
  fi
}

# ---------- 命令 ----------

cmd_install() {
  check_basics
  if [ -f "$DIR/.install" ]; then die "已经安装过了（$DIR）。更新请用 --update，卸载请用 --uninstall。"; fi
  if [ "$SKIP_NGINX" != 1 ]; then check_port80; fi
  choose_domain
  choose_password
  install_packages
  prepare_dir
  start_app
  setup_nginx
  save_state

  say "安装完成！"
  show_address
  show_credentials
  printf '    登录后：「通知设置」添加 Bot，「签到账号」添加账号（粘贴 Cookie）。获取方法见 README。\n'
  if [ "$SKIP_NGINX" != 1 ]; then printf '    云服务器还需要在厂商控制台的防火墙/安全组里放行 80%s 端口。\n' "$([ -n "$DOMAIN" ] && echo ' 和 443')"; fi
}

cmd_set_domain() {
  check_basics; require_installed
  [ "$(get_conf NGINX)" = 1 ] || die "这个安装没有使用本脚本的 nginx（NS_SKIP_NGINX），请自己配置域名和证书。"
  NS_DOMAIN="${1:-${NS_DOMAIN:-}}"
  if [ -z "$NS_DOMAIN" ]; then ask NS_DOMAIN "要绑定的域名: "; fi
  [ -n "$NS_DOMAIN" ] || die "请提供域名：bash install.sh --set-domain ns.example.com"
  PORT="$(get_conf PORT)"; PORT="${PORT:-8090}"
  choose_domain
  setup_nginx
  save_state
  say "域名已设置。"
  show_address
}

current_version() { dc exec -T web python -c 'from nsapp import VERSION; print(VERSION)' 2>/dev/null || echo "未知"; }

cmd_update() {
  check_basics; require_installed
  say "当前版本：$(current_version)"
  say "备份数据…"
  local name
  name="update-$(date -u +%Y%m%d-%H%M%S)"
  dc run --rm --no-deps -T --entrypoint python web scripts/backup.py "/data/backups/$name" >/dev/null
  dc run --rm --no-deps -T --entrypoint sh web -c 'ls -dt /data/backups/update-* 2>/dev/null | tail -n +6 | xargs -r rm -rf' || true
  say "下载最新镜像…"
  dc pull
  say "重启程序…"
  dc up -d --wait --wait-timeout 180
  say "已更新，当前版本：$(current_version)（更新前的数据备份在 Docker 卷的 /data/backups/$name，只保留最近 5 份）"
}

cmd_set_password() {
  check_basics; require_installed
  if [ -z "${NS_ADMIN_PASSWORD:-}" ] && ! have_tty; then die "需要在终端里运行，或者设置 NS_ADMIN_PASSWORD。"; fi
  choose_password
  set_admin_password
  say "管理员密码已重新设置，所有已登录的会话都已失效。"
  show_credentials
}

cmd_uninstall() {
  check_basics
  if [ ! -f "$DIR/.install" ]; then die "没有找到安装（$DIR），无需卸载。"; fi
  have_tty || die "卸载需要在终端里手动确认。"
  local domain nginx https target answer
  domain="$(get_conf DOMAIN)"; nginx="$(get_conf NGINX)"; https="$(get_conf HTTPS)"
  target="${domain:-$DIR}"
  warn "将删除：程序、配置，以及全部数据（数据库、加密密钥、备份）。这个操作无法撤销。"
  ask answer "请输入 $target 确认: "
  [ "$answer" = "$target" ] || die "输入不一致，已取消。"
  ask answer "再次输入「卸载」确认: "
  [ "$answer" = "卸载" ] || die "已取消。"

  say "停止并删除容器和数据卷…"
  dc down -v --remove-orphans
  if [ "$nginx" = 1 ]; then
    say "删除 nginx 配置和证书…"
    rm -f "$NGINX_CONF"
    if [ "$https" = 1 ] && command -v certbot >/dev/null 2>&1; then certbot delete --cert-name "$domain" --non-interactive </dev/null || true; fi
    if nginx -t >/dev/null 2>&1; then systemctl reload nginx >/dev/null 2>&1 || true; fi
  fi
  docker image rm "$IMAGE" >/dev/null 2>&1 || true
  rm -rf "$DIR"
  say "已卸载。Docker 和 nginx 本身没有删除（可能还有别的程序在用）。"
}

main() {
  case "${1:-}" in
    ""|--install)   cmd_install ;;
    --update)       cmd_update ;;
    --set-password) cmd_set_password ;;
    --set-domain)   cmd_set_domain "${2:-}" ;;
    --uninstall)    cmd_uninstall ;;
    -h|--help)      usage ;;
    *)              usage >&2; exit 2 ;;
  esac
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then main "$@"; fi
