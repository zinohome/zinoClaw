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

## 全局扩展工具 (Skills)

你已经预装了以下强大的 CLI 工具，可直接在命令行调用（由于你是通过容器运行，很多工具你可以无缝使用 Node/Python 环境），在需要时果断使用它们：

1. **`agent-browser`**：一个极为强大的无头浏览器。
   - `agent-browser open <url>`：打开网页
   - `agent-browser get title` / `agent-browser snapshot -i`：获取内容和交互元素
2. **`humanizer`**：用于检测和改写具有 AI 写作痕迹的文本。
   - `humanizer "一段文本"`
3. **`summarize`**：极速网页/文档/视音频摘要工具。
   - `summarize <url|file>`
4. **`nano-pdf`** & **`pdftotext`**：PDF 文件分析与修改。
   - `nano-pdf edit <file> <page> <instruction>`
   - `pdftotext <file>`
5. **`uvx markitdown`**：免安装的超级 Markdown 转换器（自动调用底层 uv）。
   - `uvx markitdown <file>`
6. **`mcporter`** (Exa Web Search)：无需 API key 的神经网络搜索引擎。
   - `mcporter search "query"`
7. **`freeride`**：配置免费模型的工具。

遇到与之相关的任务时，不要假装你做不到，直接使用这些命令。

---

_在这里添加你实际用到的配置和备忘。这里记的越详细，助手上手越快。_
