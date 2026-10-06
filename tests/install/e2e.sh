#!/usr/bin/env bash
# install.sh 的集成测试（Docker 部分）：
#   新装 → 备份 → 更新 → 重复更新 → 更新失败自动回滚 → 手动回滚 → 改密码 → 卸载
# 需要 root 和 Docker，以及一个已经按 docker-compose.template.yml 里的镜像名打好标签的本地镜像
#（CI 里先 docker build，服务器上可以 docker pull 后再 docker tag）。
# 全程使用独立的目录 /opt/ns-ci、端口 18090、项目名 ns-ci，并设置 NS_SKIP_NGINX=1，不碰 nginx。
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export NS_DIR=/opt/ns-ci NS_PORT="${NS_TEST_PORT:-18090}" NS_SKIP_NGINX=1 NS_SKIP_PULL=1
WORK="$(mktemp -d)"
FAILED=0

ok()  { printf 'ok   %s\n' "$1"; }
bad() { printf 'FAIL %s\n' "$1"; FAILED=1; }
check() { local name="$1"; shift; if "$@" >/dev/null 2>&1; then ok "$name"; else bad "$name"; fi; }

cleanup() {
  (cd "$NS_DIR" 2>/dev/null && docker compose down -v --remove-orphans >/dev/null 2>&1 </dev/null) || true
  if [ -d /opt/ns-ci ]; then rm -rf /opt/ns-ci; fi
  rm -rf -- "$WORK"
}
trap cleanup EXIT

login() { curl -s -o /dev/null -w '%{http_code}' -m 10 -X POST "http://127.0.0.1:$NS_PORT/api/auth/login" \
  -H 'content-type: application/json' -d "{\"username\":\"admin\",\"password\":\"$1\"}" </dev/null; }
web_image() { docker inspect --format '{{.Config.Image}}' ns-ci-web-1 2>/dev/null </dev/null; }
compose_image() { sed -n 's/^[[:space:]]*image:[[:space:]]*\([^[:space:]#]*\).*/\1/p' "$1" | head -n 1; }
run_install() { bash "$ROOT/install.sh" "$@" </dev/null 2>&1; }   # 没有终端：全部走环境变量

NEW_IMG="$(compose_image "$ROOT/docker-compose.template.yml")"
OLD_IMG="${NEW_IMG%:*}:0.0.1-test"
BAD_IMG="ns-ci-missing/none:0"
docker image inspect "$NEW_IMG" >/dev/null 2>&1 </dev/null || { echo "缺少本地镜像 $NEW_IMG：先 docker build --target runtime -t $NEW_IMG ."; exit 2; }
docker tag "$NEW_IMG" "$OLD_IMG"
for v in old new bad; do mkdir -p "$WORK/$v"; done
sed "s|image: *$NEW_IMG|image: $OLD_IMG|" "$ROOT/docker-compose.template.yml" > "$WORK/old/docker-compose.template.yml"
cp "$ROOT/docker-compose.template.yml" "$WORK/new/docker-compose.template.yml"
sed "s|image: *$NEW_IMG|image: $BAD_IMG|" "$ROOT/docker-compose.template.yml" > "$WORK/bad/docker-compose.template.yml"
export NS_ADMIN_PASSWORD='Ci-Test-Pass-1'

echo "## 新装（装的是旧版本 $OLD_IMG）"
NS_REPO_RAW="file://$WORK/old" run_install > "$WORK/install.out"; rc=$?
[ "$rc" = 0 ] && ok "install exit 0" || { bad "install exit $rc"; tail -15 "$WORK/install.out"; }
check "state file written"        test -f "$NS_DIR/.install"
check "readyz ok"                 curl -fsS -m 10 "http://127.0.0.1:$NS_PORT/readyz"
[ "$(login "$NS_ADMIN_PASSWORD")" = 200 ] && ok "login with the chosen password" || bad "login with the chosen password"
[ "$(login wrong-password-xx)" = 401 ]    && ok "wrong password rejected"        || bad "wrong password rejected"
[ "$(web_image)" = "$OLD_IMG" ]           && ok "running the old image"          || bad "running the old image ($(web_image))"
check "no random admin password file left behind" bash -c "! docker exec ns-ci-web-1 test -e /data/.admin_password"
run_install > "$WORK/again.out"; rc=$?
[ "$rc" != 0 ] && grep -q "已经安装过了" "$WORK/again.out" && ok "second install is refused" || bad "second install is refused"

echo "## 手动备份"
NS_REPO_RAW="file://$WORK/old" run_install --backup > "$WORK/backup.out"; rc=$?
[ "$rc" = 0 ] && ok "backup exit 0" || { bad "backup exit $rc"; tail -8 "$WORK/backup.out"; }
B="$(ls -d "$NS_DIR"/backups/manual-* 2>/dev/null | head -n 1)"
check "backup copied to the host (database)"    test -n "$B" -a -d "$B/app"
check "backup copied to the host (secret key)"  test -s "$B/.secret_key"

echo "## 更新到新版本"
NS_REPO_RAW="file://$WORK/new" run_install --update > "$WORK/update.out"; rc=$?
[ "$rc" = 0 ] && ok "update exit 0" || { bad "update exit $rc"; tail -12 "$WORK/update.out"; }
[ "$(web_image)" = "$NEW_IMG" ]                 && ok "running the new image"            || bad "running the new image ($(web_image))"
[ "$(login "$NS_ADMIN_PASSWORD")" = 200 ]       && ok "data and password survive the update" || bad "data and password survive the update"
[ "$(compose_image "$NS_DIR/docker-compose.yml.prev")" = "$OLD_IMG" ] && ok "previous compose kept for rollback" || bad "previous compose kept for rollback"
check "pre-update backup exists on the host"    bash -c "ls -d $NS_DIR/backups/update-* >/dev/null 2>&1"
NS_REPO_RAW="file://$WORK/new" run_install --update > "$WORK/update2.out"
grep -q "已经是最新版本" "$WORK/update2.out" && ok "second update says already latest" || bad "second update says already latest"

echo "## 更新失败 → 自动回滚"
NS_REPO_RAW="file://$WORK/bad" run_install --update > "$WORK/badupdate.out"; rc=$?
[ "$rc" != 0 ] && ok "failed update exits non-zero" || bad "failed update exits non-zero"
grep -q "自动回滚" "$WORK/badupdate.out" && ok "says it rolled back" || { bad "says it rolled back"; tail -10 "$WORK/badupdate.out"; }
[ "$(compose_image "$NS_DIR/docker-compose.yml")" = "$NEW_IMG" ] && ok "compose file restored" || bad "compose file restored"
[ "$(web_image)" = "$NEW_IMG" ]                 && ok "still running the good image"     || bad "still running the good image ($(web_image))"
check "readyz ok after rollback"                curl -fsS -m 10 "http://127.0.0.1:$NS_PORT/readyz"
[ "$(login "$NS_ADMIN_PASSWORD")" = 200 ]       && ok "login works after rollback"       || bad "login works after rollback"
check "no leftover temp compose file"           test ! -e "$NS_DIR/.compose.before"
[ "$(compose_image "$NS_DIR/docker-compose.yml.prev")" = "$OLD_IMG" ] && ok "failed update did not clobber the saved previous version" || bad "failed update did not clobber the saved previous version"

echo "## 手动回滚"
run_install --rollback > "$WORK/rollback.out"; rc=$?
[ "$rc" = 0 ] && ok "rollback exit 0" || { bad "rollback exit $rc"; tail -10 "$WORK/rollback.out"; }
[ "$(web_image)" = "$OLD_IMG" ]                 && ok "rolled back to the old image"     || bad "rolled back to the old image ($(web_image))"
[ "$(login "$NS_ADMIN_PASSWORD")" = 200 ]       && ok "login works after manual rollback" || bad "login works after manual rollback"
run_install --rollback >/dev/null
[ "$(web_image)" = "$NEW_IMG" ]                 && ok "second rollback goes forward again" || bad "second rollback goes forward again"

echo "## 改密码"
NS_ADMIN_PASSWORD='Ci-Test-Pass-2' run_install --set-password >/dev/null
[ "$(login 'Ci-Test-Pass-1')" = 401 ] && [ "$(login 'Ci-Test-Pass-2')" = 200 ] && ok "password changed" || bad "password changed"

echo "## 卸载（需要终端：用 script 模拟）"
printf 'wrong\n' | script -qec "bash $ROOT/install.sh --uninstall" /dev/null >/dev/null 2>&1
check "wrong confirmation keeps everything"     test -f "$NS_DIR/.install"
printf '%s\n卸载\n' "$NS_DIR" | script -qec "bash $ROOT/install.sh --uninstall" /dev/null >/dev/null 2>&1
check "install dir removed"                     test ! -e "$NS_DIR"
check "containers removed"                      bash -c '[ -z "$(docker ps -aq --filter name=ns-ci </dev/null)" ]'
check "data volume removed"                     bash -c '[ -z "$(docker volume ls -q --filter name=ns-ci </dev/null)" ]'

echo "## 新装后直接卸载（从没更新过，没有 .prev 文件）"
NS_REPO_RAW="file://$WORK/new" run_install > "$WORK/install2.out"; rc=$?
[ "$rc" = 0 ] && ok "second fresh install exit 0" || { bad "second fresh install exit $rc"; tail -8 "$WORK/install2.out"; }
check "no previous compose file yet"            test ! -e "$NS_DIR/docker-compose.yml.prev"
printf '%s\n卸载\n' "$NS_DIR" | script -qec "bash $ROOT/install.sh --uninstall" /dev/null >/dev/null 2>&1
check "uninstall works without a previous version (dir removed)"  test ! -e "$NS_DIR"
check "uninstall works without a previous version (containers removed)" bash -c '[ -z "$(docker ps -aq --filter name=ns-ci </dev/null)" ]'
check "uninstall works without a previous version (volume removed)"     bash -c '[ -z "$(docker volume ls -q --filter name=ns-ci </dev/null)" ]'

docker image rm "$OLD_IMG" >/dev/null 2>&1 </dev/null || true
[ "$FAILED" = 0 ] && echo "ALL PASSED" || echo "SOME TESTS FAILED"
exit "$FAILED"
