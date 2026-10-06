# 部署、升级与回滚

镜像由 `Dockerfile` 多阶段构建：Node 只用于构建前端，运行时只有 Python。到 Docker Hub 拉取基础镜像很慢时，可以用主机上已有的镜像：`--build-arg NODE_IMAGE=... --build-arg PYTHON_IMAGE=...`（经典构建器 `DOCKER_BUILDKIT=0` 会直接使用本地镜像）。`docker compose` 启动 `web` 与 `worker` 两个服务；反向代理（见 `deploy/nginx.conf`）只指向 `127.0.0.1:8090`。API 只监听本机回环地址，登录限速使用 nginx 写入的 `X-Real-IP`。

## 新安装

```bash
mkdir -p data && sudo chown -R 10001:10001 data && chmod 700 data
docker compose build
docker compose run --rm --no-deps web python -m nsapp.cli migrate   # 建表并生成实例密钥
docker compose up -d
curl --fail http://127.0.0.1:8090/readyz
```

首次启动会创建管理员；密码取自 `NS_ADMIN_PASSWORD` / `NS_ADMIN_PASSWORD_FILE`，都没有则随机生成并写入 `data/.admin_password`（权限 600，不会打印到日志）。

## 从 2.0.x 升级到 3.x

数据库结构没有变化（迁移仍是 `0001`），因此升级和回滚都不需要迁移数据。

1. **构建并测试候选镜像**（不影响线上）：
   ```bash
   docker build --target runtime -t ns-entertainment:3.0.3 .
   docker build --target test -t ns-entertainment:3.0.3-test . && docker run --rm --network none ns-entertainment:3.0.3-test
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

用 `install.sh` 或 `docker-compose.template.yml` 安装时，数据在 Docker 卷 `ns-data` 里（不是 `./data` 目录）。脚本安装的程序在 `/opt/ns-entertainment`，下面的命令都在这个目录里执行；`install.sh --update` 会在更新前自动备份到卷里的 `/data/backups/update-*`（只保留最近 5 份）。手动备份：

```bash
docker compose stop worker web
docker compose run --rm --no-deps --entrypoint python web scripts/backup.py /data/backups/我的备份
docker compose cp web:/data/backups ./backups   # 复制到当前目录，再保存到服务器之外
docker compose up -d
```

## 故障排查

- `healthz` 失败：看 `docker compose ps` 和 web 日志。
- `readyz` 503：迁移未完成，或 Worker 心跳过期（界面左下角会显示“后台服务未运行”）。
- `uncertain`（待核实）：签到或 Telegram 请求可能已成功。先人工到 NodeSeek / Telegram 核对，再决定是否手动重试；系统不会自动重发。
- 队列状态：登录后访问 `/api/system/tasks`。
- 日志只含 ID、状态码、耗时和错误码，不含 Cookie/Token/通知正文。
