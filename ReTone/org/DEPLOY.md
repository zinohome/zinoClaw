# 芮通科技 AI 数字员工团队 — 部署手册

> 依据 OpenClaw Multi-Agent Routing 官方架构
> 更新日期：2026-03-08

---

## 目录结构

```
ReTone/
├── org/
│   ├── ROSTER.md          ← 员工花名册（角色 / Bot 名 / Workspace 路径总览）
│   ├── SOUL_TEMPLATE.md   ← 全员 SOUL.md 通用模板（价值观基因）
│   └── DEPLOY.md          ← 本文件（部署手册）
│
├── config/
│   └── openclaw.json      ← OpenClaw 多路由核心配置（需填入真实 Slack Token）
│
└── workspaces/
    ├── shared/            ← 芮芮（首席助理）
    │   └── IDENTITY.md
    ├── dev-team/
    │   ├── open-lead/     ← 开远（Dev-Lead）
    │   ├── open-pm/       ← 开策（Dev-PM）
    │   ├── open-dev/      ← 开程（Dev-Eng）
    │   └── open-qa/       ← 开验（Dev-QA）
    └── research-team/
        ├── bo-lead/       ← 博远（Res-Lead）
        ├── bo-deep/       ← 博研（Res-Deep）
        ├── bo-insight/    ← 博析（Res-Insight）
        └── bo-write/      ← 博文（Res-Write）
```

---

## Phase 1：在 Slack 注册 9 个 App（外壳）

> 每个 Agent 需要独立的 Slack App，以便在群聊中拥有独立头像和身份

**操作步骤（每个 App 重复 9 次）：**

1. 访问 [api.slack.com/apps](https://api.slack.com/apps) → Create New App → From Scratch
2. App 名称按下表填写：

| App 名称 | Bot 用户名 | 对应 Agent |
|---|---|---|
| `Vera` | `@Vera` | Vera（首席助理）|
| `Dev-Lead` | `@Dev-Lead` | 开远 |
| `Dev-PM` | `@Dev-PM` | 开策 |
| `Dev-Eng` | `@Dev-Eng` | 开程 |
| `Dev-QA` | `@Dev-QA` | 开验 |
| `Res-Lead` | `@Res-Lead` | 博远 |
| `Res-Deep` | `@Res-Deep` | 博研 |
| `Res-Insight` | `@Res-Insight` | 博析 |
| `Res-Write` | `@Res-Write` | 博文 |

3. 为每个 App 开启 **Socket Mode**，获取 `App-Level Token（xapp-开头）`
4. 在 OAuth & Permissions 中添加以下 Scopes：
   - `app_mentions:read`、`channels:history`、`chat:write`、`groups:history`
   - `im:history`、`im:write`、`reactions:write`、`users:read`
5. 订阅事件：`app_mention`、`message.channels`、`message.im`
6. 安装到 Workspace，获取 `Bot User OAuth Token（xoxb-开头）`
7. 将所有 Token 填入 `ReTone/config/openclaw.json`

---

## Phase 2：在容器中建立 Workspace 目录

在宿主机（或通过SSH进入容器后），执行以下命令创建 9 个隔离的 workspace：

```bash
# 在容器内执行（确保目录属于 abc 用户）
mkdir -p /config/.openclaw/{workspace,dev-lead-workspace,dev-pm-workspace,dev-eng-workspace,dev-qa-workspace,res-lead-workspace,res-deep-workspace,res-insight-workspace,res-write-workspace}
chown -R abc:abc /config/.openclaw/
```

---

## Phase 3：从项目目录同步 Workspace 模板

将本项目 `ReTone/workspaces/` 下的文件，拷贝到容器的对应目录：

```bash
# 每个 Agent 的 IDENTITY.md 拷贝到对应 workspace（以开远为例）
docker cp ReTone/workspaces/dev-team/open-lead/IDENTITY.md webclaw:/config/.openclaw/dev-lead-workspace/IDENTITY.md

# 通用 SOUL.md 拷贝到所有 workspace（逐一执行，并按角色个性化修改）
for dir in workspace dev-lead-workspace dev-pm-workspace dev-eng-workspace dev-qa-workspace \
           res-lead-workspace res-deep-workspace res-insight-workspace res-write-workspace; do
  docker cp ReTone/org/SOUL_TEMPLATE.md webclaw:/config/.openclaw/$dir/SOUL.md
done
```

---

## Phase 4：部署 openclaw.json

将 Token 填写完毕的配置文件部署到容器：

```bash
docker cp ReTone/config/openclaw.json webclaw:/config/.openclaw/openclaw.json
chown abc:abc /config/.openclaw/openclaw.json
```

然后重启服务：
```bash
docker restart webclaw
```

---

## Phase 5：验证多 Agent 上线

重启后，观察容器日志：
```bash
docker logs webclaw -f --tail=100 | grep -E "(agent|slack|connected|error)"
```

**期望看到：**
- `[slack] vera connected`
- `[slack] dev-lead connected`
- `[slack] res-lead connected`
- …（9 个 Agent 全部连接成功）

---

## 最小可行验证（MVP 测试顺序）

1. 先只激活 **3 个**：`vera` + `dev-lead` + `res-lead`（注释掉其他账户的 Token）
2. 在 Slack 中分别私信这 3 个 Bot，确认他们都能独立响应
3. 把他们拉进同一个测试群，用 `@Dev-Lead` 下个任务，看群聊通信是否正常
4. 验证成功后，启用全部 9 个 Agent

---

## 防坑提示

> **回音壁问题（最重要！）**
> 所有 Agent 的 SOUL.md 必须包含：
> `"我只在被明确 @ 提及时才在群聊中回复，不插嘴其他 Agent 正在处理的对话。"`
> 否则，任意一个 Agent 的发言都可能触发其他 8 个同时回复，造成无限循环！
