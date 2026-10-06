#!/usr/bin/env bash
# shellcheck disable=SC2034  # PORT / SKIP_NGINX / DOMAIN 等变量由 source 进来的 install.sh 使用
# install.sh 的集成测试（nginx / HTTPS 部分）。在一个临时的 Debian 容器里运行，不会碰宿主机：
#   docker run --rm -v "$PWD:/src:ro" python:3.12-slim bash /src/tests/install/nginx.sh
# 容器里装真实的 nginx，直接调用 install.sh 里的函数；systemctl / certbot / 公网 IP 用假的替代。
set -u
SRC="${SRC:-/src}"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/dev/null 2>&1 && apt-get install -y -qq nginx curl openssl >/dev/null 2>&1
command -v nginx >/dev/null || { echo "nginx 安装失败"; exit 2; }

cat > /tmp/backend.py <<'PY'
from http.server import BaseHTTPRequestHandler, HTTPServer
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = f"backend saw X-Real-IP={self.headers.get('X-Real-IP')} Proto={self.headers.get('X-Forwarded-Proto')} Host={self.headers.get('Host')}\n".encode()
        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
HTTPServer(("127.0.0.1", 18090), H).serve_forever()
PY
python3 /tmp/backend.py & sleep 1

# shellcheck source=/dev/null
source "$SRC/install.sh"
set +eE +o pipefail; trap - ERR          # install.sh 打开了 errexit；这里要测失败的情况
systemctl() { case "$*" in *reload*) nginx -s reload; sleep 1 ;; *) return 0 ;; esac; }
certbot() { CERTBOT_ARGS="$*"; return "${FAKE_CERTBOT_RC:-0}"; }
public_ip() { printf '203.0.113.10'; }
PORT=18090; SKIP_NGINX=0
FAILED=0
ok()  { printf 'ok   %s\n' "$1"; }
bad() { printf 'FAIL %s\n' "$1"; FAILED=1; }
expect() { local name="$1" got="$2" want="$3"; if [[ "$got" == *"$want"* ]]; then ok "$name"; else bad "$name  (got: ${got:0:160})"; fi; }
http() { curl -s -m 5 -o /dev/null -w '%{http_code} %{redirect_url}' "$@"; }

nginx   # 用原装配置启动

echo "## A. 对照：不停用 nginx 自带站点，IP 模式的配置会冲突"
render_nginx selfsigned "" "$PORT" > "$NGINX_CONF"; make_selfsigned_cert 203.0.113.10 >/dev/null
expect "duplicate default server is reported" "$(nginx -t 2>&1)" "duplicate default server"
rm -f "$NGINX_CONF" "$TLS_CRT" "$TLS_KEY"

echo "## B. 不绑定域名：自签名 HTTPS，80 跳转到 443"
DOMAIN=""; setup_nginx >/dev/null 2>&1
expect "stock welcome site was disabled"      "[$(ls /etc/nginx/sites-enabled/)]" "[]"
expect "self-signed cert has the IP in its SAN" "$(openssl x509 -in "$TLS_CRT" -noout -ext subjectAltName 2>&1)" "IP Address:203.0.113.10"
expect "private key is mode 600"              "$(stat -c %a "$TLS_KEY")" "600"
expect "state: SELFSIGNED=1 HTTPS=0"          "SELFSIGNED=$SELFSIGNED HTTPS=$HTTPS" "SELFSIGNED=1 HTTPS=0"
expect "http redirects to https"              "$(http -H 'Host: 203.0.113.10' http://127.0.0.1/)" "301 https://203.0.113.10/"
expect "plain http never reaches the app"     "$(curl -s -m 5 -H 'Host: 203.0.113.10' http://127.0.0.1/)" ""
body_http="$(curl -s -m 5 -H 'Host: 203.0.113.10' http://127.0.0.1/)"; [[ "$body_http" != *"backend saw"* ]] && ok "no backend response over http" || bad "backend reachable over http"
expect "https is proxied to the app"          "$(curl -sk -m 5 -H 'Host: 203.0.113.10' https://127.0.0.1/)" "backend saw X-Real-IP=127.0.0.1 Proto=https"
expect "client-supplied X-Real-IP is overwritten" "$(curl -sk -m 5 -H 'X-Real-IP: 9.9.9.9' https://127.0.0.1/)" "X-Real-IP=127.0.0.1"
expect "nginx config passes nginx -t"         "$(nginx -t 2>&1)" "successful"

echo "## C. 绑定域名，证书申请成功"
DOMAIN=ns.example.com; CERTBOT_ARGS=""; FAKE_CERTBOT_RC=0; setup_nginx >/dev/null 2>&1
expect "state: HTTPS=1 SELFSIGNED=0"          "SELFSIGNED=$SELFSIGNED HTTPS=$HTTPS" "SELFSIGNED=0 HTTPS=1"
expect "certbot got the right arguments"      "$CERTBOT_ARGS" "--nginx -d ns.example.com --non-interactive --agree-tos --redirect --register-unsafely-without-email"
expect "self-signed files removed after a real cert" "$([ -e "$TLS_CRT" ] || [ -e "$TLS_KEY" ] && echo present || echo gone)" "gone"
expect "domain is served"                     "$(curl -s -m 5 -H 'Host: ns.example.com' http://127.0.0.1/)" "backend saw X-Real-IP=127.0.0.1"

echo "## D. 绑定域名，证书申请失败 → 降级为自签名 HTTPS（不会留明文）"
DOMAIN=ns.example.com; CERTBOT_ARGS=""; FAKE_CERTBOT_RC=1; NS_EMAIL=me@example.com setup_nginx >/tmp/d.out 2>&1
expect "certbot got -m when NS_EMAIL is set"  "$CERTBOT_ARGS" "-m me@example.com"
expect "state: SELFSIGNED=1 HTTPS=0"          "SELFSIGNED=$SELFSIGNED HTTPS=$HTTPS" "SELFSIGNED=1 HTTPS=0"
expect "user is told it fell back"            "$(cat /tmp/d.out)" "已降级为自签名证书"
expect "http redirects to https"              "$(http -H 'Host: ns.example.com' http://127.0.0.1/)" "301 https://ns.example.com/"
expect "https works with the fallback cert"   "$(curl -sk -m 5 -H 'Host: ns.example.com' https://127.0.0.1/)" "backend saw"
expect "cert covers the domain"               "$(openssl x509 -in "$TLS_CRT" -noout -ext subjectAltName 2>&1)" "DNS:ns.example.com"

echo "## E. 用户自己改过默认站点：不动它，冲突时报错并撤销"
rm -f "$NGINX_CONF" "$TLS_CRT" "$TLS_KEY"; nginx -s reload; sleep 1
cat > /etc/nginx/sites-available/default <<'CONF'
server { listen 80 default_server; server_name _; location / { proxy_pass http://127.0.0.1:9999; } }
CONF
ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default
DOMAIN=""; out="$( ( setup_nginx ) 2>&1 )"
expect "conflict is reported"                 "$out" "nginx 配置检查没通过"
[ -e "$NGINX_CONF" ] && bad "our config was rolled back" || ok "our config was rolled back"
[ -L /etc/nginx/sites-enabled/default ] && ok "the customised site was left alone" || bad "the customised site was left alone"

[ "$FAILED" = 0 ] && echo "ALL PASSED" || echo "SOME TESTS FAILED"
exit "$FAILED"
