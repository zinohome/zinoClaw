# webclaw 定制 KDE 桌面镜像 — 构建说明

## 目录结构

构建前请确认以下文件结构完整：

```
zinoClaw/
├── Dockerfile                          # 镜像构建文件（本次定制）
├── BUILD.md                            # 本说明文档
└── docker-customize/
    ├── Fonts/
    │   └── JetBrainsMono/              # JetBrains Mono 全套字体文件 (.ttf)
    └── Themes/
        ├── com.github.varlesh.greybird.tar.gz
        ├── com.github.varlesh.materia-dark.tar.gz
        ├── com.github.varlesh.rounded.tar.gz
        └── exposeair-global-30.tar.xz
```

---

## 镜像内容说明

| 步骤 | 内容 |
|------|------|
| 第零步 | 替换 apt 源为清华镜像 + `apt dist-upgrade` 全量系统更新 |
| 第一步 | 安装常用基础工具（ping、netstat、curl、wget、git、vim、htop 等）|
| 第二步 | 安装 JetBrains Mono 字体到系统字体目录，刷新字体缓存 |
| 第三步 | 安装 4 个 KDE Plasma Look-and-Feel 主题包 |

---

## 构建步骤

### 前提条件

- Docker 已安装并运行
- 已登录私有 Harbor 仓库

```bash
docker login harbor.naivehero.top:8443
```

### 第一步：进入项目根目录

**必须在 `zinoClaw/` 目录下执行构建**，因为 `Dockerfile` 中的 `COPY` 路径是相对于此目录的。

```bash
cd /path/to/zinoClaw
```

### 第二步：构建镜像

```bash
docker build \
  -t harbor.naivehero.top:8443/baseimages/linuxserver/webtop:zino-kde-custom \
  .
```

> **说明**
> - `-t` 指定镜像名称和 tag
> - 末尾的 `.` 代表当前目录为构建上下文（包含 `docker-customize/` 等资源）
> - 首次构建耗时较长（`dist-upgrade` 会更新系统包），后续构建命中缓存会快很多

如需查看详细构建日志（推荐首次构建时使用）：

```bash
docker build --progress=plain \
  -t harbor.naivehero.top:8443/baseimages/linuxserver/webtop:zino-kde-custom \
  .
```

### 第三步：验证镜像构建结果

```bash
# 查看镜像是否生成
docker images | grep zino-kde-custom

# 进入镜像内部验证内容（可选）
docker run --rm -it \
  harbor.naivehero.top:8443/baseimages/linuxserver/webtop:zino-kde-custom \
  bash -c "
    echo '=== 字体 ===' && fc-list | grep JetBrains
    echo '=== 主题 ===' && ls /usr/share/plasma/look-and-feel/
    echo '=== 命令 ===' && which ping git curl wget vim htop
  "
```

预期输出示例：

```
=== 字体 ===
/usr/share/fonts/truetype/JetBrainsMono/JetBrainsMono-Medium.ttf: JetBrains Mono,JetBrains Mono Medium:style=Medium,Regular
...
=== 主题 ===
com.github.varlesh.greybird
com.github.varlesh.materia-dark
com.github.varlesh.rounded
ExposeAir
=== 命令 ===
/usr/bin/ping  /usr/bin/git  /usr/bin/curl  /usr/bin/wget  /usr/bin/vim  /usr/bin/htop
```

### 第四步：推送到 Harbor

```bash
docker push harbor.naivehero.top:8443/baseimages/linuxserver/webtop:zino-kde-custom
```

---

## 部署更新

构建并推送完成后，修改 `docker-compose.yml` 中的 `image` 字段：

```yaml
services:
  webclaw:
    image: harbor.naivehero.top:8443/baseimages/linuxserver/webtop:zino-kde-custom
    # ... 其余配置不变
```

拉取新镜像并重启容器：

```bash
docker compose pull webclaw
docker compose up -d webclaw
```

---

## 注意事项

> **已有配置卷的情况**
> 如果 `/data/webclaw/config` 卷已存在旧的 KDE 配置，主题和字体不会自动生效，需要在桌面手动切换：
> - **字体**：系统设置 → 外观 → 字体 → 选择 `JetBrains Mono Medium`
> - **主题**：系统设置 → 外观 → 全局主题 → 选择已安装主题

> **重新构建时跳过缓存**
> 如需强制从头重建（如基础镜像已更新）：
> ```bash
> docker build --no-cache \
>   -t harbor.naivehero.top:8443/baseimages/linuxserver/webtop:zino-kde-custom \
>   .
> ```
