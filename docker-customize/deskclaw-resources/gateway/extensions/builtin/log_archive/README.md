# 日志归档

自动将每轮对话保存到本地文件，支持 JSONL 和 Markdown 两种格式。

## 配置项

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| enabled | bool | 是 | 是否启用 |
| priority | int | 否 | 执行优先级，数字越小越先执行，默认 100 |
| dir | string | 是 | 日志输出目录，支持 `~` 展开 |
| format | string | 否 | 输出格式：`jsonl`（默认）或 `markdown` |

## 输出格式

### JSONL（默认）

每天一个文件（如 `2026-03-25.jsonl`），每行一个 JSON 对象：

```json
{"ts": "2026-03-25T10:30:00+00:00", "type": "turn", "session": "desktop:abc123", "user": "帮我写个脚本", "response": "好的..."}
{"ts": "2026-03-25T10:30:01+00:00", "type": "tool_call", "tool": "exec", "decision": "allowed", "duration_ms": 500}
```

### Markdown

每天一个文件（如 `2026-03-25.md`），按时间排列：

```markdown
## 10:30:00 — desktop:abc123

**User:** 帮我写个脚本

**Assistant:** 好的...

---
```

## 示例配置

```json
{
  "enabled": true,
  "dir": "~/.deskclaw/logs",
  "format": "jsonl"
}
```
