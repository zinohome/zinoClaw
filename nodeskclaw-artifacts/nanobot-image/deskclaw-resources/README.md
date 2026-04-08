# DeskClaw 资源说明

此目录用于保存可提交、可用于 Docker 构建的 DeskClaw 资源快照。

构建 `Dockerfile` 时只会读取：

- `docker-customize/deskclaw-resources/gateway/`
- `docker-customize/deskclaw-resources/nanobot/`
- `docker-customize/deskclaw-resources/skills/`

## 准备资源

先确保本地已有：

- `projects/DeskClaw.app/Contents/Resources/gateway`
- `projects/DeskClaw.app/Contents/Resources/nanobot`
- `projects/DeskClaw/skills`

然后执行：

```bash
python3 docker-customize/scripts/prepare-deskclaw-resources.py
```

执行后会把上述资源复制到本目录下，后续构建不再依赖 `projects/`。

容器启动时会将 `skills/` 幂等同步到：

- `/config/.deskclaw/nanobot/workspace/skills`

同步策略为只补充缺失文件，不覆盖你已修改的技能内容。
