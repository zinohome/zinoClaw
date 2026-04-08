# jobs.json Schema 参考

## 顶层结构

```json
{
  "version": 1,
  "jobs": [ /* job 对象数组 */ ]
}
```

- `version`：必填，当前为 1
- `jobs`：必填，job 对象数组

## Job 对象必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 唯一标识，建议 UUID |
| `agentId` | string | 如 `"main"` |
| `name` | string | 任务名称 |
| `schedule` | object | 调度配置 |
| `sessionTarget` | string | `"main"` 或 `"isolated"` |
| `payload` | object | 执行内容，必须与 sessionTarget 匹配 |

## sessionTarget 与 payload 对应关系（重要）

| sessionTarget | payload.kind | 提示内容字段 | 说明 |
|---------------|--------------|--------------|------|
| `main` | `systemEvent` | `text` | 主会话，通过 heartbeat 执行 |
| `isolated` | `agentTurn` | `message` | 独立 cron 会话，专用 agent turn |

**常见错误**：
- `sessionTarget: "isolated"` 却用 `payload.kind: "message"` → 会报 `isolated job requires payload.kind=agentTurn`
- `sessionTarget: "main"` 却用 `payload.kind: "message"` → 应改为 `systemEvent` + `text`
- `agentTurn` 用 `text` 而非 `message` → 应使用 `message`

## Schedule 结构

### Cron 表达式

```json
{
  "kind": "cron",
  "expr": "0 11 * * *",
  "tz": "Asia/Shanghai",
  "staggerMs": 0
}
```

### 一次性提醒

```json
{
  "kind": "at",
  "at": "2026-02-01T16:00:00Z"
}
```

### 固定间隔

```json
{
  "kind": "every",
  "everyMs": 3600000
}
```

## 完整示例

### main 会话 job（systemEvent）

```json
{
  "id": "e1697265-dd86-4d6f-949e-a0d6cb1ee2dc",
  "agentId": "main",
  "name": "每日11点饮食提醒",
  "enabled": true,
  "schedule": {
    "kind": "cron",
    "expr": "20 11 * * *",
    "tz": "Asia/Shanghai"
  },
  "sessionTarget": "main",
  "wakeMode": "now",
  "payload": {
    "kind": "systemEvent",
    "text": "今天打算吃什么？"
  }
}
```

### isolated 会话 job（agentTurn）

```json
{
  "id": "7db91b49-0df3-4379-b3d6-70c611f0aff7",
  "agentId": "main",
  "name": "每日凌晨3点写日记",
  "enabled": true,
  "schedule": {
    "kind": "cron",
    "expr": "0 3 * * *",
    "tz": "Asia/Shanghai"
  },
  "sessionTarget": "isolated",
  "wakeMode": "now",
  "payload": {
    "kind": "agentTurn",
    "message": "现在是凌晨3点，执行每日日记任务。\n\n步骤：\n1. 获取今天的日期..."
  }
}
```

## JSON 追加规则（避免解析失败）

向 `jobs` 数组追加新 job 时：

1. **确保前一元素末尾有逗号**：`},` 后接 `{`，不能是 `}` 后直接 `{`
2. 使用 `json.dumps(..., indent=2)` 或手动校验 JSON 格式
3. 写入前必须执行 `scripts/validate-jobs-json.sh` 校验

## 参考

- [OpenClaw Cron Jobs 文档](https://docs.clawd.bot/automation/cron-jobs)
- [cron-mastery](https://clawhub.ai/i-mw/cron-mastery)
