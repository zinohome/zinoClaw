# webclaw 镜像构建说明

## 镜像构建架构

本项目分**两层**构建，顺序不能颠倒：

```
第一层: zino-kde-custom  (KDE 桌面底包，一次性构建，长期复用)
    ↓  FROM
第二层: zino-kde-openclaw (OpenClaw 服务层，按需更新)
```

| 镜像 | Dockerfile | 作用 |
|------|------------|------|
| `zino-kde-custom` | `Dockerfile` | KDE 桌面定制底包（清华源、工具、字体、主题）|
| `zino-kde-openclaw` | `Dockerfile.openclaw` | 在底包上安装 Node.js 22 + OpenClaw，注册为 s6 服务 |

---

## 目录结构

```
zinoClaw/
├── Dockerfile                          # 第一层: KDE 桌面底包
├── Dockerfile.openclaw                 # 第二层: OpenClaw 服务层
├── BUILD.md                            # 本说明文档
└── docker-customize/
    ├── Fonts/
    │   └── JetBrainsMono/              # JetBrains Mono 全套字体文件 (.ttf)
    ├── Themes/
    │   ├── com.github.varlesh.greybird.tar.gz
    │   ├── com.github.varlesh.materia-dark.tar.gz
    │   ├── com.github.varlesh.rounded.tar.gz
    │   └── exposeair-global-30.tar.xz
    └── Software/
        ├── code_1.109.5-1771531656_amd64.deb  # VS Code
        └── cursor_2.5.26_amd64.deb            # Cursor
```

---

## 前提条件

- Docker 已安装并运行
- 已登录私有 Harbor 仓库

```bash
docker login harbor.naivehero.top:8443
```

**所有构建命令必须在 `zinoClaw/` 目录下执行：**

```bash
cd /path/to/zinoClaw
```

---

## 第一层：构建 KDE 桌面底包

> **只需构建一次！** 底包包含耗时的 `dist-upgrade`，之后作为长期基础镜像复用。

### 内容说明

| 步骤 | 内容 |
|------|------|
| 第零步 | 替换 apt 源为清华镜像 + `apt dist-upgrade` 全量系统更新 |
| 第一步 | 安装常用基础工具（ping、netstat、curl、wget、git、vim、htop 等）|
| 第二步 | 安装 JetBrains Mono 字体，刷新字体缓存 |
| 第三步 | 安装 4 个 KDE Plasma Look-and-Feel 主题包 |
| 第四步 | 安装 VS Code（本地 .deb，自动注入官方 apt 源）|
| 第五步 | 安装 Cursor（本地 .deb，自动注入官方 apt 源）|
| 第六步 | 安装 Antigravity（Google Cloud Artifact Registry apt 源）|
| 第七步 | 安装 Google Chrome（Google 官方 apt 源）|

### 构建命令

```bash
# 标准构建
docker build \
  -t harbor.naivehero.top:8443/baseimages/linuxserver/webtop:zino-kde-custom \
  .

# 显示详细日志（推荐首次构建时使用）
docker build --progress=plain \
  -t harbor.naivehero.top:8443/baseimages/linuxserver/webtop:zino-kde-custom \
  .
```

### 验证底包内容

```bash
docker run --rm -it \
  harbor.naivehero.top:8443/baseimages/linuxserver/webtop:zino-kde-custom \
  bash -c "
    echo '=== 字体 ===' && fc-list | grep JetBrains
    echo '=== 主题 ===' && ls /usr/share/plasma/look-and-feel/
    echo '=== 命令 ===' && which ping git curl wget vim htop
    echo '=== 软件 ===' && which code cursor antigravity google-chrome-stable
  "
```

预期输出：
```
=== 字体 ===
/usr/share/fonts/truetype/JetBrainsMono/JetBrainsMono-Medium.ttf: JetBrains Mono,JetBrains Mono Medium:style=Medium,Regular
...
=== 主题 ===
com.github.varlesh.greybird   com.github.varlesh.materia-dark
com.github.varlesh.rounded    ExposeAir
=== 命令 ===
/usr/bin/ping  /usr/bin/git  /usr/bin/curl  /usr/bin/wget  /usr/bin/vim  /usr/bin/htop
=== 软件 ===
/usr/bin/code  /usr/bin/cursor  /usr/bin/antigravity  /usr/bin/google-chrome-stable
```

### 推送底包到 Harbor

```bash
docker push harbor.naivehero.top:8443/baseimages/linuxserver/webtop:zino-kde-custom
```

---

## 第二层：构建 OpenClaw 服务层

> **底包推送完成后**，再构建此层。openclaw 版本更新时只需重新构建这一层。

### 内容说明

| 步骤 | 内容 |
|------|------|
| 第一步 | 安装 Node.js 22（openclaw 硬性依赖）|
| 第二步 | `npm install -g openclaw@latest` 全局安装 |
| 第三步 | 注册 `openclaw-gateway` 为 s6-overlay `longrun` 服务（随容器启动自动运行）|

> **为什么用 s6-overlay 注册而不是 `/custom-services.d`？**
>
> 来自 [linuxserver 官方文档](https://docs.linuxserver.io/general/container-customization)：
> `/custom-services.d` 和 `/custom-cont-init.d` **必须通过 docker volume 挂载**才能被 s6 扫描，
> 在 Dockerfile 里直接创建不会生效。
> 将服务注册到 `/etc/s6-overlay/s6-rc.d/` 才是"烧进镜像"的正确方式。

### 构建命令

```bash
# 使用 -f 指定 Dockerfile.openclaw
docker build --progress=plain \
  -f Dockerfile.openclaw \
  -t harbor.naivehero.top:8443/baseimages/linuxserver/webtop:zino-kde-openclaw \
  .
```

### 验证 OpenClaw 安装

```bash
docker run --rm -it \
  harbor.naivehero.top:8443/baseimages/linuxserver/webtop:zino-kde-openclaw \
  bash -c "
    echo '=== Node.js ===' && node --version
    echo '=== openclaw ===' && openclaw --version
    echo '=== s6 服务 ===' && ls /etc/s6-overlay/s6-rc.d/openclaw-gateway/
    echo '=== user2 注册 ===' && ls /etc/s6-overlay/s6-rc.d/user2/contents.d/ | grep openclaw
  "
```

预期输出：
```
=== Node.js ===
v22.x.x
=== openclaw ===
openclaw/x.x.x ...
=== s6 服务 ===
run  type
=== user2 注册 ===
openclaw-gateway
```

### 推送到 Harbor

```bash
docker push harbor.naivehero.top:8443/baseimages/linuxserver/webtop:zino-kde-openclaw
```

---

## 部署 docker-compose

将 `image` 改为最终镜像，并确保 **18789 端口**（openclaw gateway）已暴露：

```yaml
services:
  webclaw:
    image: harbor.naivehero.top:8443/baseimages/linuxserver/webtop:zino-kde-openclaw
    container_name: webclaw
    hostname: webclaw
    shm_size: '1gb'
    security_opt:
      - seccomp:unconfined
      - no-new-privileges:false
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Asia/Shanghai
      - CUSTOM_USER=zhangjun
      - PASSWORD=bgt56yhn@Passw0rd
      - LC_ALL=zh_CN.UTF-8
      - NO_GAMEPAD=true
      - TITLE=webclaw
      # openclaw gateway 认证 token（强烈建议设置）
      - OPENCLAW_GATEWAY_TOKEN=your-long-random-token-here
    volumes:
      - /data/webclaw/config:/config
    ports:
      - 18789:18789    # OpenClaw Gateway
      - 3201:3001      # KDE 桌面 (HTTPS)
    restart: unless-stopped
    networks:
      - 1panel-network

networks:
  1panel-network:
    external: true
```

拉取并重启：

```bash
docker compose pull webclaw
docker compose up -d webclaw
```

---

## 注意事项

> **KDE 字体/主题手动设置**
> 如果 `/data/webclaw/config` 卷已存在旧配置，需在 KDE 桌面手动切换：
> - **字体**：系统设置 → 外观 → 字体 → 选择 `JetBrains Mono Medium`
> - **主题**：系统设置 → 外观 → 全局主题 → 选择已安装主题

> **openclaw 配置文件位置**
> 容器内 openclaw 的配置和数据存放在 `/config/.openclaw/`（映射到宿主机 `/data/webclaw/config/.openclaw/`），
> 重新部署容器不会丢失数据。

> **openclaw 版本升级**
> 只需重新构建第二层并推送：
> ```bash
> docker build --no-cache --progress=plain \
>   -f Dockerfile.openclaw \
>   -t harbor.naivehero.top:8443/baseimages/linuxserver/webtop:zino-kde-openclaw .
> docker push harbor.naivehero.top:8443/baseimages/linuxserver/webtop:zino-kde-openclaw
> docker compose up -d webclaw
> ```

> **强制底包从头重建**（底包需要更新时）
> ```bash
> docker build --no-cache --progress=plain \
>   -t harbor.naivehero.top:8443/baseimages/linuxserver/webtop:zino-kde-custom .
> docker push harbor.naivehero.top:8443/baseimages/linuxserver/webtop:zino-kde-custom
> # 然后再重建第二层
> ```
