"""Internal system documentation for the DeskClaw agent (read_docs tool).

These docs help the agent understand its own architecture, config mechanics,
and internal workings.  They are NOT user-facing.
"""

from __future__ import annotations

DOCS: dict[str, str] = {}

DOCS["system"] = """\
# DeskClaw 系统架构

## 组件
Electron 主进程（窗口/插件）→ Gateway 子进程（FastAPI + MCP）→ Agent 内核；另有 Gateway 侧性能层（并行工具、缓存、记忆压缩等）。

## 要点
- **exec PATH**：导入 `AgentLoop` 前 `exec_tool_patch` 替换 `ExecTool`；仅子进程 `env` **前置** gateway-venv、`sys.prefix`/scripts、`~/.deskclaw/uv`（若有），不改 `os.environ`；`pathAppend` 仍在末尾。
- **并行工具 / Steering / 审批串行**：多工具并发；用户插话合并进当前会话并可中断后续工具；并行时审批弹窗逐个出。
- **配置**：写入前校验；成功启动后备份；连续失败 3 次回滚 `config.last-good`。

## 路径
默认路径为 `~/.deskclaw/nanobot/config.json`（核心）、`config.last-good`、`nanobot/workspace/`（含 `skills/`）、`~/.deskclaw/skills/`、`tool-allowlist.json`；若设置了 `NANOBOT_CONFIG_PATH` / `DESKCLAW_NANOBOT_HOME` / `DESKCLAW_HOME`，则以环境变量解析结果为准。

## 重启
`restart_gateway`（改配置，校验后重启网关）；`restart_deskclaw`（整应用，默认关、需 allowlist）。
"""

DOCS["configuration"] = """\
# LLM 配置

## 结构（节选）
`agents.defaults`（workspace、model、provider、temperature、maxTokens、maxToolIterations…）、`providers.*`、`tools`（含 `mcpServers`）、`channels`。

## agents.defaults 关键字段
| 字段 | 默认 | 说明 |
|------|------|------|
| model | — | 使用的模型名称 |
| maxTokens | 8192 | LLM 最大输出 token |
| temperature | 0.1 | 模型温度 |
| maxToolIterations | 40 | 单轮对话最大工具调用次数，达到后停止并提示继续 |
| contextWindowTokens | 65536 | 上下文窗口大小 |

## 流程
`get_config` → `update_config`（值须为合法 JSON 片段，写入前 Pydantic 校验）→ `restart_gateway`。启用 channel 时会自动补 `allowFrom` 等默认值。

## MCP
增删改用 `mcp_server_list` / `mcp_server_add` / `mcp_server_remove`，勿手改 JSON；改完 `restart_gateway`。可与设置里 MCP 页一致。

## 示例
`update_config("<点号路径>", "<JSON 片段>")`，如 `agents.defaults.model` + `'"gpt-4o"'`；`providers.custom.api_base`、`agents.defaults.temperature`、`agents.defaults.provider` 同理。

## Provider
`custom`：OpenAI 兼容，要 api_key + api_base。`anthropic`：要 api_key，路由带 anthropic/ 前缀。api_key 空且已配 api_base → 走自带鉴权端点。
"""

DOCS["security"] = """\
# 安全与审批

调工具前：内置策略（enforce 可拦危险操作）→ 插件 interactive_approval（白名单 + 弹窗）。

工具返回后：安全层 **结果管道**（`ToolSecurityLayer`）依次做可选的 **超大输出截断**（默认上限为内核 `_TOOL_RESULT_MAX_CHARS` 的 **10 倍**，仅拦极端体积；可在 `tool-security-policy.json` 的 `result_pipeline.max_output_chars` 覆盖）、**enforce 下 DLP**，再执行用户插件的 `transform_result`；审计仍走 `on_after`。

**完全访问**：设置「安全」或 `POST /security/full-access`，跳过审批。

**白名单** 默认在 `~/.deskclaw/tool-allowlist.json`，若设置了 `DESKCLAW_HOME` 则跟随其目录：命令侧「始终允许」→ 如 `exec:git *`；工具侧 → 无限制 `{}` 或 `figma:*`；`exec:* *` / `*:*` 为全开（强警示）。有限制规则显蓝色 badge，可 hover 删路径或升级为无限制。

**Bot 控制**：设置「安全」里开关是否允许 MCP 改沙箱/网络/循环守卫。

**循环守卫**：检测工具调用死循环，详见 `read_docs("loop_guard")`。

**工具调用上限**：`agents.defaults.maxToolIterations`（默认 40），控制单轮对话最大工具调用次数。达到上限后 Agent 会停止并提示用户发送「继续」。可用 `set_max_tool_iterations` 工具动态调整，无需重启。
"""

DOCS["sandbox"] = """\
# 沙箱

**模式**：`transparent`（默认，宿主机） / `isolated`（Docker 或 Podman 容器）。

**网络**（仅 isolated）：`none` / `host` / 自定义网络名。

**工具**：`sandbox_status` → `sandbox_set_mode` / `sandbox_set_network` → 改网络后须 `sandbox_restart`；切模式本身可立即生效。工作区挂到容器 `/workspace/...`。
"""

DOCS["cron"] = """\
# 定时任务

工具 `cron`，`action`：`add` / `list` / `remove`（删不可恢复）。

**存储**：`<agents.defaults.workspace>/cron/jobs.json`（非 config 旁旧路径；启动时从 `get_cron_dir()` 迁移一次）。

**add 参数**：`message`；`every_seconds` 或 `cron_expr`（+ 可选 `tz`）或 `at`（ISO，一次后删）。
"""

DOCS["diagnostics"] = """\
# 诊断

**日志**：`~/.deskclaw/logs/main.log`（及按日归档，约 10MB 轮转）；托盘 → 打开日志。

**工具**：`get_health`、`get_config`、`sandbox_status`。

**处理**：配置错 → `update_config` + `restart_gateway`；网关僵 → `restart_gateway`；沙箱 → `sandbox_restart`。Key/额度 → 设置 API 或账户；无容器运行时 → 装 Docker/Podman；网络/代理让用户自查。超大工具输出由 Gateway 安全层结果管道处理（见 `read_docs("security")`）。

**升级外**：反复崩溃、疑似缺陷或安全问题 → 收集日志，引导 GitHub Issues。
"""

DOCS["loop_guard"] = """\
# 循环守卫 (Loop Guard)

检测并阻止 Agent 陷入工具调用死循环（重复调用、连续失败）。

## 配置文件
`~/.deskclaw/loop-guard.json`（不存在则使用默认值）。

## 参数
| 字段 | 默认 | 说明 |
|------|------|------|
| enabled | true | 是否启用 |
| sensitivity | "default" | 预设灵敏度，覆盖下方阈值 |
| max_duplicate_calls | 3 | 相同工具+参数调用次数上限 |
| max_consecutive_errors | 5 | 连续失败次数上限 |
| max_failed_per_turn | 25 | 单轮失败总次数上限 |
| turn_reset_seconds | 60 | 超时自动重置计数器 |

## 灵敏度预设
| 预设 | duplicate | consecutive | failed |
|------|-----------|-------------|--------|
| conservative | 3 | 5 | 20 |
| default | 3 | 5 | 25 |
| relaxed | 5 | 8 | 40 |

## 工具
`loop_guard_status` 查看当前配置；`loop_guard_set_sensitivity` / `loop_guard_set_enabled` 修改配置（需 Bot 控制权限）。

## 工具调用上限
`get_max_tool_iterations` 查看当前 `maxToolIterations`；`set_max_tool_iterations(value)` 修改（需 Bot 控制权限），修改后需 `restart_gateway` 生效。默认 40，建议范围 10~200。
"""

DOCS["channels"] = """\
# 外部消息通道

`channels.*` 在 config.json；改完 **`restart_gateway`**。内置通道多为长连接 WebSocket，一般无需公网 IP。

## 字段表

### feishu
| 字段 | 必填 | 说明 |
|------|------|------|
| enabled | 是 | 是否启用 |
| appId | 是 | App ID（cli_） |
| appSecret | 是 | App Secret |
| allowFrom | 是 | open_id 列表，`["*"]` 全开 |
| groupPolicy | 否 | `mention`（默认）/ `open`（群全开） |
| react_emoji | 否 | 收到消息点表情；`""` 关闭；可 `OnIt`/`Get`/`OK` |
| streaming | 否 | CardKit 分段刷新，默认 `true`；`false` 整段一次发。关流式：`update_config("channels.feishu.streaming", "false")` 或改 JSON + `restart_gateway`（GUI 可能无此项；与飞书客户端「消息显示」无关） |

### qq
| 字段 | 必填 | 说明 |
|------|------|------|
| enabled | 是 | 是否启用 |
| appId | 是 | QQ 开放平台 AppID |
| secret | 是 | QQ 开放平台 AppSecret |
| allowFrom | 是 | 允许的用户 openid 列表，`["*"]` 允许所有人 |
| msgFormat | 否 | `"plain"`（默认）或 `"markdown"` |

### dingtalk
| 字段 | 必填 | 说明 |
|------|------|------|
| enabled | 是 | 是否启用 |
| clientId | 是 | 钉钉 AppKey (Client ID) |
| clientSecret | 是 | 钉钉 AppSecret (Client Secret) |
| allowFrom | 是 | 允许的用户 staff ID 列表，`["*"]` 允许所有人 |

### wecom
| 字段 | 必填 | 说明 |
|------|------|------|
| enabled | 是 | 是否启用 |
| botId | 是 | 企微智能机器人 Bot ID |
| secret | 是 | 企微智能机器人 Secret |
| allowFrom | 是 | 允许的用户 ID 列表，`["*"]` 允许所有人 |

### weixin（ilink 个人）
| 字段 | 必填 | 说明 |
|------|------|------|
| enabled | 是 | 是否启用 |
| token | 是 | Bot Token（DeskClaw 聊天/设置里可扫码；或 venv 里 `nanobot channels login weixin`） |
| allowFrom | 是 | `["*"]` 或收窄 |
| baseUrl / cdnBaseUrl / stateDir / pollTimeout | 否 | 默认见 ilink 文档；stateDir 空 → 数据目录下 `weixin/` |

#### Agent 代扫码（无聊天 GUI、必须用工具链时）

优先让用户在 **DeskClaw 聊天/设置 → 微信 → 扫码登录**；或本机 **`~/.deskclaw/gateway-venv/bin/nanobot channels login weixin`**。以下仅内置 `nanobot.channels.weixin`，与外部 channel 包无关。

1. **取码**：无 token 时请求 `GET {baseUrl}/ilink/bot/get_bot_qrcode?bot_type=3`（无 Bearer；请求头与 `WeixinChannel` 一致，如 `iLink-App-ClientVersion`）。从响应取 **`qrcode_img_content`**（嵌进二维码的**内容字符串**，常为 `https://liteapp.weixin.qq.com/...`），**不是**可直接 `<img src>` 的图 URL，也不要让用户用浏览器打开代替扫码。同时记下 **`qrcode` / `qrcode_id`** 供步骤 4。
2. **成图**：用 Gateway venv 的 Python，`qrcode`（需 Pillow）把上一步字符串生成 **PNG**，写入数据目录下**带时间戳的唯一路径**（避免缓存旧图），例如 `~/.deskclaw/nanobot/weixin/qr/login_qr_<unix_ts>.png`（与 `get_runtime_subdir("weixin")` 一致即可）。
3. **发图**：用 **`message` 工具**，`content` 说明请用户微信扫码，`media` 传该 PNG 的**绝对路径**。
4. **轮询**：`GET {baseUrl}/ilink/bot/get_qrcode_status?qrcode=<步骤1的 id>`（头同内置）。**每次 `exec` 只请求一次**（接口会长阻塞）；根据 `wait` / `scaned`/`scanned` / `expired` / `confirmed` 决定下一轮是否再调工具。**禁止**在单次 `exec` 里用 `for` 连续长轮询，否则易超时、码过期。
5. **落配置**：`confirmed` 后取 **`bot_token`**（及响应里的 **`baseurl`/`baseUrl`** 若有），`update_config` 写入 `channels.weixin` 并启用，`restart_gateway`。实现细节以 **`WeixinChannel._qr_login`** 为准。

## 示例
```
update_config("channels.feishu.enabled", "true")
update_config("channels.feishu.appId", '"cli_xxx"')
update_config("channels.feishu.appSecret", '"xxx"')
update_config("channels.feishu.allowFrom", '["*"]')
update_config("channels.feishu.streaming", "false")   # 可选：关流式
update_config("channels.weixin.enabled", "true")
update_config("channels.weixin.token", '"<token>"')
update_config("channels.weixin.allowFrom", '["*"]')
```

## 注意
`allowFrom` 常 `["*"]`；收窄时 ID 多从日志取。凭证错往往静默失败，查日志。建机器人步骤见 `user_faq("channels")`。

## 飞书 MCP（channel 就绪并 restart 后可问用户是否要接）

**Proxy（推荐）** `mcp_server_add`，`type=streamableHttp`，`url=https://feishu-mcp.nodesk.tech/mcp`，`headers` 含 `X-Feishu-App-Id` / `X-Feishu-App-Secret`（同 `channels.feishu`），`tool_timeout=30`。

**个人文档**：用户打开 `https://feishu-mcp.nodesk.tech/auth/feishu?app_id=…&app_secret=…` 授权，把返回的 `user_id` 再塞进 headers 的 `X-Feishu-User-Id` 后 `mcp_server_add` 更新。

**官方内测 MCP**：用户有 URL 时用其替换 `url`；否则用 Proxy。
"""
