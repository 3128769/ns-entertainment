/** Chinese wording for status values and error codes returned by the API. */

export type Tone = 'ok' | 'bad' | 'info' | 'muted'

interface StatusInfo {
  label: string
  tone: Tone
}

const STATUS: Record<string, StatusInfo> = {
  success: { label: '成功', tone: 'ok' },
  already: { label: '已签到', tone: 'ok' },
  notified: { label: '已通知', tone: 'ok' },
  ok: { label: '正常', tone: 'ok' },
  baseline: { label: '已建立基线', tone: 'info' },
  no_match: { label: '无新命中', tone: 'muted' },
  failed: { label: '失败', tone: 'bad' },
  timeout: { label: '超时', tone: 'bad' },
  notify_failed: { label: '通知失败', tone: 'bad' },
  expired: { label: 'Cookie 已过期', tone: 'bad' },
  nodeseek_auth_expired: { label: 'Cookie 已过期', tone: 'bad' },
  nodeseek_cookie_expired: { label: 'Cookie 已过期', tone: 'bad' },
  nodeseek_cloudflare_blocked: { label: '访问受阻', tone: 'bad' },
  uncertain: { label: '待核实', tone: 'bad' },
}

export function statusInfo(status: string | null | undefined): StatusInfo {
  if (!status) return { label: '未执行', tone: 'muted' }
  return STATUS[status] ?? { label: status, tone: 'muted' }
}

/** Statuses that mean "something needs attention". */
export const FAILED_STATUSES = new Set(['failed', 'timeout', 'notify_failed', 'expired', 'uncertain'])

const TEXT: Record<string, string> = {
  // generic
  NETWORK_ERROR: '网络连接失败，请检查网络后重试',
  REQUEST_FAILED: '请求失败，请稍后重试',
  INTERNAL_ERROR: '服务器内部错误，请查看日志',
  VALIDATION_FAILED: '提交的内容不符合要求，请检查后重试',
  UNAUTHORIZED: '登录已失效，请重新登录',
  INVALID_USERNAME_OR_PASSWORD: '用户名或密码错误',
  RATE_LIMITED: '尝试次数过多，请 5 分钟后再试',
  FRONTEND_NOT_BUILT: '前端资源缺失，请重新构建镜像',
  // accounts
  NODESEEK_ACCOUNT_NOT_FOUND: '账号不存在，可能已被删除，请刷新后重试',
  NODESEEK_NAME_REQUIRED: '请填写账号名称',
  NODESEEK_NAME_CONFLICT: '账号名称已存在',
  NODESEEK_COOKIE_REQUIRED: '请填写完整有效的 Cookie',
  NODESEEK_SCHEDULE_INVALID: '请填写有效的签到时间',
  NODESEEK_SCHEDULE_RANGE_INVALID: '随机区间的开始与结束时间不能相同',
  NODESEEK_KEYWORDS_INVALID: '关键词最多填写 20 个',
  NODESEEK_MONITOR_CONFIG_REQUIRED: '请补全关键词、通知 Bot 和 Chat ID',
  NODESEEK_MONITOR_DISABLED: '该账号未启用关键词监听',
  NODESEEK_MESSAGE_CONFIG_REQUIRED: '请补全私信通知 Bot 和 Chat ID',
  NODESEEK_MESSAGE_DISABLED: '该账号未启用私信通知',
  NODESEEK_OFFLINE_CONFIG_REQUIRED: '请补全掉线通知 Bot 和 Chat ID',
  NODESEEK_OFFLINE_DISABLED: '该账号未启用掉线通知',
  NODESEEK_ACCOUNT_BUSY: '该账号正在执行任务，请稍后再试',
  // check-in
  NODESEEK_REQUEST_FAILED: '签到请求失败，请稍后重试',
  NODESEEK_CONNECT_FAILED: '无法连接 NodeSeek，请检查网络或代理',
  NODESEEK_RESULT_UNCERTAIN: '签到结果待核实，请先检查 NodeSeek；系统不会自动重复签到',
  NODESEEK_AUTH_EXPIRED: 'Cookie 已过期，请重新登录 NodeSeek 后更新',
  NODESEEK_COOKIE_EXPIRED: 'Cookie 已过期，请重新登录 NodeSeek 后更新',
  NODESEEK_CLOUDFLARE_BLOCKED: '访问受阻，暂时无法确认 Cookie 状态，请稍后重试',
  NODESEEK_COOKIE_OK: 'Cookie 有效',
  // keyword monitor
  NODESEEK_MONITOR_BASELINE_SAVED: '已按原帖发布时间建立基线，旧帖不会补发',
  NODESEEK_MONITOR_NO_MATCH: '本次检查没有新的原帖命中',
  NODESEEK_MONITOR_NOTIFIED: '关键词命中通知已发送',
  NODESEEK_MONITOR_NOTIFY_FAILED_WILL_RETRY: '通知发送失败，后续检查将重试',
  NODESEEK_MONITOR_FAILED: '监听检查失败，请稍后重试',
  NODESEEK_FEED_INVALID: '未能读取帖子列表，请稍后重试',
  // private messages
  NODESEEK_MESSAGE_BASELINE_SAVED: '已建立私信基线，后续将检查新私信',
  NODESEEK_MESSAGE_NO_MATCH: '本次检查无新私信',
  NODESEEK_MESSAGE_NOTIFIED: '私信通知已发送',
  NODESEEK_MESSAGE_NOTIFY_FAILED_WILL_RETRY: '私信通知发送失败，后续检查将重试',
  NODESEEK_MESSAGE_FAILED: '私信检查失败，请稍后重试',
  // cookie check
  NODESEEK_OFFLINE_NOTIFIED: 'Cookie 过期通知已发送',
  NODESEEK_OFFLINE_FAILED: '掉线检查失败，请稍后重试',
  NODESEEK_OFFLINE_NOTIFY_FAILED: '掉线通知发送失败',
  // proxies
  PROXY_NOT_FOUND: '代理不存在',
  PROXY_IN_USE: '代理仍被账号使用，请先更换这些账号的代理',
  PROXY_NAME_CONFLICT: '代理名称已存在',
  PROXY_NAME_INVALID: '请填写代理名称',
  PROXY_URL_INVALID: '代理链接格式无效',
  PROXY_CONNECT_FAILED: '代理连接失败',
  // bots and telegram
  BOT_NOT_FOUND: '通知 Bot 不存在，请刷新后重试',
  BOT_FIELDS_INVALID: '请补全名称、有效的 Token 和 Chat ID',
  BOT_CONFIG_INVALID: '请补全 Bot Token 和通知接收人',
  TELEGRAM_TOKEN_INVALID: 'Bot Token 无效或已失效，请在连接页更新；未发送的通知将重试',
  TELEGRAM_CHAT_UNAVAILABLE: '接收人不可用，请核对 Chat ID 并先向 Bot 发送 /start',
  TELEGRAM_CHAT_FORBIDDEN: 'Bot 无权发送通知，请解除屏蔽或检查群组权限',
  TELEGRAM_RATE_LIMITED: 'Telegram 发送受限，后续检查将重试',
  TELEGRAM_TIMEOUT: 'Telegram 请求超时，请稍后重试',
  TELEGRAM_NETWORK_FAILED: '无法连接 Telegram，请检查服务器网络',
  TELEGRAM_RESPONSE_INVALID: 'Telegram 返回异常，请稍后重试',
  TELEGRAM_SEND_FAILED: 'Telegram 发送失败，请核对接收人和 Bot 权限',
  TELEGRAM_RESULT_UNCERTAIN: '通知结果待核实；系统不会盲目重发',
  TELEGRAM_RETRY_WAIT: '通知等待有限重试',
  TELEGRAM_RETRY_EXHAUSTED: '通知多次发送失败，已停止重试',
  // background tasks
  WORKER_UNAVAILABLE: '后台任务服务尚未就绪，请稍后重试',
  TASK_QUEUE_FULL: '任务队列繁忙，请稍后重试',
  TASK_LEASE_LOST: '任务已被其他进程接管，本次结果已丢弃',
  TASK_DISABLED: '任务已停用',
  TASK_EXECUTION_FAILED: '任务执行失败，请查看日志',
  WORKER_INTERRUPTED: '后台任务被中断，将自动重试',
  ACCOUNT_DELETED: '账号已删除',
}

/** Human text for an error code or message; unknown codes are shown as-is with underscores softened. */
export function describe(codeOrText: string | null | undefined): string {
  const value = String(codeOrText ?? '').trim()
  if (!value) return '等待执行'
  return TEXT[value] ?? TEXT[value.toUpperCase()] ?? value.replaceAll('_', ' ')
}

export const SOURCE_LABEL: Record<string, string> = { scheduled: '自动执行', manual: '手动执行' }
