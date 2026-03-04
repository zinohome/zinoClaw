# TOOLS.md - 工具速查卡

_本地配置、快捷命令、环境信息。这里记的是「你的」特定配置，不是通用说明。_

## 环境信息

- **运行方式**：Docker 容器（zinoClaw）
- **Workspace 路径**：`/config/.openclaw/workspace`
- **配置文件**：`/config/.openclaw/openclaw.json`
- **Chromium**：`/usr/bin/chromium`（无头模式）

## IM 频道

- **Slack**：Socket Mode，Bot 名称 ReToneClaw
  - 频道策略：`groupPolicy: open`，`dmPolicy: allowlist`

## 常用操作

```bash
# 查看容器日志
docker logs <容器名> -f

# 重启服务
docker restart <容器名>
```

---

_在这里添加你实际用到的配置和备忘。这里记的越详细，助手上手越快。_
