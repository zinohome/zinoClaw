# Webhook Notifier

对话完成或工具调用时发送 HTTP POST 通知到指定 URL。

## 配置

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| enabled | bool | 是 | 是否启用 |
| priority | int | 否 | 执行优先级，数字越小越先执行，默认 100 |
| url | string | 是 | 接收通知的 URL |
| events | string[] | 否 | 订阅的事件列表，默认 `["turn_end"]` |
| template | object/null | 否 | 自定义 payload 模板，`null` 则发送原始 JSON |
| secret | string | 否 | HMAC-SHA256 签名密钥，留空则不签名 |
| timeout | number | 否 | HTTP 请求超时秒数，默认 5 |

## 模板变量

在 `template` 中使用 `{变量名}` 占位符，发送时自动替换为实际值：

| 变量 | 说明 |
|------|------|
| `{event}` | 事件类型：`turn_end` / `turn_start` / `tool_call` |
| `{event_label}` | 事件中文标签：对话完成 / 对话开始 / 工具调用 |
| `{timestamp}` | 时间戳 `YYYY-MM-DD HH:MM:SS` (UTC) |
| `{session}` | 会话标识 |
| `{response}` | Agent 回复内容（turn_end 时有值） |
| `{message}` | 用户消息内容（turn_start 时有值） |
| `{tool}` | 工具名称（tool_call 时有值） |
| `{decision}` | 安全决策（tool_call 时有值） |
| `{duration_ms}` | 工具执行耗时 ms（tool_call 时有值） |
| `{summary}` | 预格式化的单行摘要 |

## 可订阅事件

- `turn_end` — 一轮对话结束
- `turn_start` — 一轮对话开始
- `tool_call` — 工具调用完成

## 示例配置

### 不使用模板（直接发送原始 JSON）

```json
{
  "enabled": true,
  "url": "https://your-server.com/deskclaw-hook",
  "events": ["turn_end", "tool_call"],
  "secret": "your-secret-key"
}
```

### 飞书 Webhook 机器人

```json
{
  "enabled": true,
  "url": "https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
  "events": ["turn_end", "tool_call"],
  "template": {
    "msg_type": "text",
    "content": {
      "text": "[DeskClaw] {summary}"
    }
  }
}
```

### Slack Incoming Webhook

```json
{
  "enabled": true,
  "url": "https://hooks.slack.com/services/xxx",
  "events": ["turn_end"],
  "template": {
    "text": "[DeskClaw] {summary}"
  }
}
```

### Discord Webhook

```json
{
  "enabled": true,
  "url": "https://discord.com/api/webhooks/xxx",
  "events": ["turn_end"],
  "template": {
    "content": "[DeskClaw] {summary}"
  }
}
```

### 自定义详细格式

```json
{
  "enabled": true,
  "url": "https://your-server.com/hook",
  "events": ["turn_end"],
  "template": {
    "msg_type": "text",
    "content": {
      "text": "事件: {event_label}\n时间: {timestamp}\n会话: {session}\n回复: {response}"
    }
  }
}
```

## HMAC 签名验证

配置 `secret` 后，每个请求会附带 `X-DeskClaw-Signature` header（SHA256 HMAC hex digest），接收端可用来验证请求合法性。
