# 安全说明

## 报告漏洞

发现安全问题请**不要**在公开 Issue 里贴细节。请使用本仓库 **Security → Report a vulnerability**（GitHub 私密报告）；如果该入口不可用，先开一个只写“有安全问题想私下沟通”的 Issue。

## 这个程序处理什么敏感信息

- NodeSeek 账号 Cookie、代理凭据、Telegram Bot Token：使用实例密钥（`data/.secret_key`）做 Fernet 加密后存入数据库；接口永远不会回传这些值。
- 管理员密码：scrypt 哈希；登录令牌只以 SHA-256 存储，24 小时过期。
- 日志只包含 ID、状态码、耗时和错误码，不含 Cookie、Token 或通知正文。

## 部署时请注意

- **必须放在 HTTPS 反向代理后面**；应用只监听 `127.0.0.1:8090`。
- `data/` 目录（数据库和 `.secret_key`）不要提交到任何仓库，备份要加密保存。
- 登录限速依赖反向代理写入的 `X-Real-IP`，不要把 8090 端口直接暴露到公网。
- 怀疑 Cookie 或 Token 泄露时：在 NodeSeek 修改密码（旧 Cookie 随即失效），在 `@BotFather` 重新生成 Token，并用 `python -m nsapp.cli set-admin-password` 更换管理员密码。
