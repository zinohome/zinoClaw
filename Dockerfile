# =============================================================================
# webclaw KDE 桌面底包
# 基础镜像: lscr.io/linuxserver/webtop:ubuntu-kde (官方 Ubuntu KDE 桌面)
# 功能:
#   0. 替换 apt 源为清华镜像 + apt dist-upgrade 全量系统更新
#   1. 安装 Ubuntu 常用基础命令工具
#   2. 安装 JetBrains Mono 字体（字体文件，不做 KDE 配置，桌面自行设置）
#   3. 安装 KDE Plasma Look-and-Feel 主题包
#   4. 安装 VS Code（本地 .deb，自动注入官方 apt 源供后续更新）
#   5. 安装 Cursor（本地 .deb，自动注入官方 apt 源供后续更新）
#   6. 安装 Antigravity（via Google Cloud Artifact Registry apt 源）
#   7. 安装 Google Chrome（via Google apt 源）
#
# 构建命令 (在 zinoClaw/ 目录下执行):
#   docker build --progress=plain \
#     -t harbor.naivehero.top:8443/baseimages/linuxserver/webtop:zino-kde-custom \
#     .
# =============================================================================

FROM lscr.io/linuxserver/webtop:ubuntu-kde

# -----------------------------------------------------------------------------
# 第零步: 替换 apt 源为国内官方归档镜像，并全量更新系统软件包
# 使用国内源加速构建，避免访问境外源超时
# apt dist-upgrade 比 apt upgrade 更彻底，可处理依赖关系变化的包
# 注意: 使用 printf 逐行写入，避免 heredoc 被 Dockerfile linter 误判
# -----------------------------------------------------------------------------

# 备份原始 sources.list 并替换为镜像源（Ubuntu 24.04 Noble）
RUN printf '%s\n' \
    '# Ubuntu 软件镜像站 - Ubuntu 24.04 Noble' \
    '# 默认注释了源码镜像以提高 apt update 速度' \
    'deb http://cn.archive.ubuntu.com/ubuntu/ noble main restricted universe multiverse' \
    '# deb-src http://cn.archive.ubuntu.com/ubuntu/ noble main restricted universe multiverse' \
    'deb http://cn.archive.ubuntu.com/ubuntu/ noble-updates main restricted universe multiverse' \
    '# deb-src http://cn.archive.ubuntu.com/ubuntu/ noble-updates main restricted universe multiverse' \
    'deb http://cn.archive.ubuntu.com/ubuntu/ noble-backports main restricted universe multiverse' \
    '# deb-src http://cn.archive.ubuntu.com/ubuntu/ noble-backports main restricted universe multiverse' \
    'deb http://cn.archive.ubuntu.com/ubuntu/ noble-security main restricted universe multiverse' \
    '# deb-src http://cn.archive.ubuntu.com/ubuntu/ noble-security main restricted universe multiverse' \
    > /etc/apt/sources.list && \
    # 更新软件包索引
    apt-get update && \
    # 全量升级所有已安装包（dist-upgrade 可处理依赖关系变更的升级）
    apt-get dist-upgrade -y && \
    # 清理缓存，减小镜像体积
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# 第一步: 安装基础命令工具
# 同时安装后续步骤所需的 gnupg / ca-certificates（添加第三方 apt 源必需）
# -----------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    # 网络诊断工具
    iputils-ping \
    # 网络接口管理工具 (ifconfig, netstat 等)
    net-tools \
    # HTTP/HTTPS 下载工具
    curl \
    wget \
    # 版本控制
    git \
    # 文件解压工具
    unzip \
    xz-utils \
    # 文本处理常用工具
    vim \
    nano \
    # 进程查看工具
    htop \
    # 系统信息
    lsb-release \
    # 字体配置工具 (fc-cache 命令所在包)
    fontconfig \
    # apt 第三方源所需（gpg 密钥、https 传输）
    gnupg \
    ca-certificates \
    apt-transport-https \
    # Python 运行时（DeskClaw gateway / nanobot-webui）
    python3 \
    python3-venv \
    python3-pip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# 第二步: 安装 JetBrains Mono 字体
# 字体文件复制到 /usr/share/fonts/truetype/JetBrainsMono/ (系统级字体目录)
# fc-cache -fv 刷新字体缓存，使字体全局生效
# -----------------------------------------------------------------------------
COPY docker-customize/Fonts/JetBrainsMono/ /usr/share/fonts/truetype/JetBrainsMono/
RUN fc-cache -fv

# -----------------------------------------------------------------------------
# 第三步: 安装 KDE Plasma Look-and-Feel 主题
# 标准安装目录: /usr/share/plasma/look-and-feel/
# 包含主题:
#   - com.github.varlesh.greybird   (Greybird KDE Look-and-Feel)
#   - com.github.varlesh.materia-dark (Materia Dark KDE Look-and-Feel)
#   - com.github.varlesh.rounded    (Rounded KDE Look-and-Feel)
#   - ExposeAir                     (ExposeAir Global Theme)
# -----------------------------------------------------------------------------
COPY docker-customize/Themes/ /tmp/themes/

RUN set -eux; \
    mkdir -p /usr/share/plasma/look-and-feel/; \
    for pkg in \
    com.github.varlesh.greybird.tar.gz \
    com.github.varlesh.materia-dark.tar.gz \
    com.github.varlesh.rounded.tar.gz; \
    do \
    echo ">>> 安装主题: $pkg"; \
    tar -xzf /tmp/themes/$pkg -C /usr/share/plasma/look-and-feel/; \
    done; \
    echo ">>> 安装主题: exposeair-global-30.tar.xz"; \
    tar -xJf /tmp/themes/exposeair-global-30.tar.xz -C /usr/share/plasma/look-and-feel/; \
    rm -rf /tmp/themes; \
    echo ">>> 已安装的 KDE 主题:"; \
    ls /usr/share/plasma/look-and-feel/

# -----------------------------------------------------------------------------
# 第四步: 安装 VS Code
# 通过 Microsoft 官方 apt 源安装，不需要本地 .deb 文件
# 使用 DEB822 格式（Ubuntu 推荐的新格式）写入 apt 源配置
# 每次构建都会安装 Microsoft 仓库最新的 code 版本
# 注意: packages.microsoft.com 在美国，构建时可能需要等待
# -----------------------------------------------------------------------------
RUN wget -qO- https://packages.microsoft.com/keys/microsoft.asc | \
    gpg --dearmor > /tmp/microsoft.gpg && \
    install -D -o root -g root -m 644 /tmp/microsoft.gpg /usr/share/keyrings/microsoft.gpg && \
    rm -f /tmp/microsoft.gpg && \
    # 使用 DEB822 格式写入 VS Code apt 源
    printf '%s\n' \
    'Types: deb' \
    'URIs: https://packages.microsoft.com/repos/code' \
    'Suites: stable' \
    'Components: main' \
    'Architectures: amd64,arm64,armhf' \
    'Signed-By: /usr/share/keyrings/microsoft.gpg' \
    > /etc/apt/sources.list.d/vscode.sources && \
    apt-get update && \
    apt-get install -y --no-install-recommends code && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# 第五步: 安装 Cursor
# 使用本地 .deb 文件安装，安装过程会自动注入 Cursor 官方 apt 源
# 保证容器内可通过 apt 进行后续更新
# -----------------------------------------------------------------------------
COPY docker-customize/Software/cursor_3.0.13_amd64.deb /tmp/cursor.deb

RUN apt-get install -y /tmp/cursor.deb && \
    apt-get clean && \
    rm -f /tmp/cursor.deb && \
    rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# 第六步: 安装 Antigravity
# 通过 Google Cloud Artifact Registry apt 源安装
# 步骤: 添加 GPG 密钥 → 添加 apt 源 → apt install antigravity
# 注意: 此源服务器在美国，如构建超时可多试几次
# -----------------------------------------------------------------------------
RUN mkdir -p /etc/apt/keyrings && \
    # 下载并添加 Antigravity 仓库签名密钥
    curl -fsSL https://us-central1-apt.pkg.dev/doc/repo-signing-key.gpg | \
    gpg --dearmor --yes -o /etc/apt/keyrings/antigravity-repo-key.gpg && \
    # 添加 Antigravity apt 源
    printf 'deb [signed-by=/etc/apt/keyrings/antigravity-repo-key.gpg] https://us-central1-apt.pkg.dev/projects/antigravity-auto-updater-dev/ antigravity-debian main\n' \
    > /etc/apt/sources.list.d/antigravity.list && \
    # 更新缓存并安装
    apt-get update && \
    apt-get install -y --no-install-recommends antigravity && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# 第七步: 安装 Google Chrome
# 通过 Google 官方 apt 源安装 google-chrome-stable
# 安装后 /etc/apt/sources.list.d/google-chrome.list 会保留，可在容器内更新
# 注意: Google 源服务器在美国，如构建超时可多试几次
# -----------------------------------------------------------------------------
RUN curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | \
    gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg && \
    printf 'deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main\n' \
    > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends google-chrome-stable && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# 第八步: 预置 nanobot-webui 补丁覆盖机制（不改第三方源码仓库）
# 说明:
#   - 将本仓库 patches/nanobot-webui 下的文件放入镜像
#   - 若镜像中已安装 webui 包，则在构建时自动覆盖对应模块文件
#   - 若尚未安装 webui，则跳过；可在后续层或容器启动阶段再次执行同逻辑
# -----------------------------------------------------------------------------
COPY patches/nanobot-webui/ /opt/patches/nanobot-webui/
COPY docker-customize/scripts/apply_webui_patches.py /opt/patches/apply_webui_patches.py

RUN python3 -c "import importlib.util, pathlib, shutil; \
spec=importlib.util.find_spec('webui'); \
patch_root=pathlib.Path('/opt/patches/nanobot-webui'); \
print('[patch] webui installed:', bool(spec)); \
 \
 \
 \
target_root=pathlib.Path(spec.submodule_search_locations[0]) if spec and spec.submodule_search_locations else None; \
 \
 \
 \
[(p.parent.mkdir(parents=True, exist_ok=True), shutil.copy2(str(src), str(p)), print('[patch] applied', src.relative_to(patch_root))) \
 for src in patch_root.rglob('*') if src.is_file() and target_root is not None \
 for p in [target_root / src.relative_to(patch_root)] ]"

# -----------------------------------------------------------------------------
# 第九步: 预置 DeskClaw gateway 资源与一键启动脚本
# -----------------------------------------------------------------------------
COPY docker-customize/deskclaw-resources/ /opt/deskclaw/resources/
COPY docker-customize/scripts/start-deskclaw-webui.sh /usr/local/bin/start-deskclaw-webui

RUN chmod +x /usr/local/bin/start-deskclaw-webui /opt/patches/apply_webui_patches.py

# -----------------------------------------------------------------------------
# 元数据标签
# -----------------------------------------------------------------------------
LABEL maintainer="zhangjun" \
    description="webclaw KDE 桌面底包 - VSCode + Cursor + Antigravity + Chrome + JetBrains Mono + KDE 主题" \
    base="lscr.io/linuxserver/webtop:ubuntu-kde" \
    version="2.1.0"
