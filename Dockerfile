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
    '# 默认注释了源码镜像以提高 apt update 速度，如有需要可自行取消注释' \
    'deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ noble main restricted universe multiverse' \
    '# deb-src https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ noble main restricted universe multiverse' \
    'deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ noble-updates main restricted universe multiverse' \
    '# deb-src https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ noble-updates main restricted universe multiverse' \
    'deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ noble-backports main restricted universe multiverse' \
    '# deb-src https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ noble-backports main restricted universe multiverse' \
    '' \
    '# 以下安全更新软件源为官方源配置' \
    'deb http://security.ubuntu.com/ubuntu/ noble-security main restricted universe multiverse' \
    '# deb-src http://security.ubuntu.com/ubuntu/ noble-security main restricted universe multiverse' \
    '' \
    # 预发布软件源，不建议启用' \
    # '# deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ noble-proposed main restricted universe multiverse' \
    # '# # deb-src https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ noble-proposed main restricted universe multiverse' \
    > /etc/apt/sources.list && \
    # 【架构修复方案：配置 Apt Pinning 安全降级高版本组件而不卸载依赖】
    # 将游离的高版本 python3-setuptools/pkg-resources 强制定向到 noble 官方稳定版
    printf "Package: python3-setuptools python3-pkg-resources\nPin: release n=noble*\nPin-Priority: 1001\n" > /etc/apt/preferences.d/99-downgrade-python && \
    # 更新软件包索引
    apt-get update && \
    # 全量升级所有已安装包（通过 --allow-downgrades 允许触发自动降级修复）
    apt-get dist-upgrade -y --allow-downgrades && \
    # 清理缓存，减小镜像体积
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# 第一步: 安装基础命令工具
# 同时安装后续步骤所需的 gnupg / ca-certificates（添加第三方 apt 源必需）
# 注: LinuxServer 底包可能预装了不兼容的高版本 python3-setuptools, 导致安装 pip 冲突，在此先尝试卸载
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
COPY docker-customize/feishu-copilot-handoff-0.2.56.vsix /tmp/feishu-copilot-handoff-0.2.56.vsix

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
    mkdir -p /opt/vscode-extensions /custom-cont-init.d && \
    code --install-extension /tmp/feishu-copilot-handoff-0.2.56.vsix --no-sandbox --user-data-dir /tmp --extensions-dir /opt/vscode-extensions && \
    # 保留原 .vsix 包至 /opt/vscode-extensions 目录备用
    cp /tmp/feishu-copilot-handoff-0.2.56.vsix /opt/vscode-extensions/ && \
    printf "#!/bin/bash\nmkdir -p /config/.vscode/extensions\ncp -rn /opt/vscode-extensions/* /config/.vscode/extensions/\nchown -R abc:abc /config/.vscode\n" > /custom-cont-init.d/99-install-vscode-extensions && \
    chmod +x /custom-cont-init.d/99-install-vscode-extensions && \
    rm -rf /tmp/feishu-copilot-handoff-0.2.56.vsix /tmp/Cache /tmp/CachedData /tmp/Code /tmp/Crashpad /tmp/DawnCache /tmp/GPUCache && \
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
# 第六步: 安装 Antigravity 和 Cockpit Tools
# 通过 Google Cloud Artifact Registry apt 源安装 Antigravity
# 通过 GitHub Release 下载安装 Cockpit Tools
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
    # 安装 cockpit tools
    wget -qO /tmp/cockpit-tools.deb https://github.com/jlcodes99/cockpit-tools/releases/download/v0.21.3/Cockpit.Tools_0.21.3_amd64.deb && \
    apt-get install -y /tmp/cockpit-tools.deb && \
    rm -f /tmp/cockpit-tools.deb && \
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
# 第八步: 预置 DeskClaw 资源 + nanobot-webui 补丁，并在构建期完成安装
# 运行期不再 pip install，容器启动即就绪
# -----------------------------------------------------------------------------
COPY docker-customize/deskclaw-resources/ /opt/deskclaw/resources/
COPY patches/nanobot-webui/ /opt/patches/nanobot-webui/
COPY docker-customize/scripts/apply_webui_patches.py /opt/patches/apply_webui_patches.py
COPY docker-customize/scripts/start-deskclaw-webui.sh /usr/local/bin/start-deskclaw-webui
COPY docker-customize/scripts/restart-deskclaw.sh /usr/local/bin/restart-deskclaw.sh

RUN set -eux; \
    chmod +x /usr/local/bin/start-deskclaw-webui /usr/local/bin/restart-deskclaw.sh /opt/patches/apply_webui_patches.py; \
    python3 -m venv /opt/deskclaw/gateway-venv; \
    /opt/deskclaw/gateway-venv/bin/pip install -U pip setuptools wheel; \
    WHEEL_PATH="$(ls /opt/deskclaw/resources/nanobot/nanobot_ai-*.whl | head -n 1)"; \
    /opt/deskclaw/gateway-venv/bin/pip install "$WHEEL_PATH"; \
    /opt/deskclaw/gateway-venv/bin/pip install \
      "fastapi>=0.115.0" \
      "uvicorn>=0.34.0" \
      "websockets>=14.0" \
      "wecom-aibot-sdk-python>=0.1.5" \
      "qrcode[pil]>=8.0" \
      "pycryptodome>=3.20.0"; \
    python3 -m venv /opt/deskclaw/webui-venv; \
    /opt/deskclaw/webui-venv/bin/pip install -U pip setuptools wheel; \
    /opt/deskclaw/webui-venv/bin/pip install nanobot-webui; \
    /opt/deskclaw/webui-venv/bin/python /opt/patches/apply_webui_patches.py /opt/patches/nanobot-webui

# -----------------------------------------------------------------------------
# 第九步: 注册 s6 服务（webtop 启动时自动拉起 deskclaw-gateway + webui）
# -----------------------------------------------------------------------------
RUN mkdir -p /etc/s6-overlay/s6-rc.d/svc-deskclaw && \
    echo "longrun" > /etc/s6-overlay/s6-rc.d/svc-deskclaw/type && \
    printf "#!/usr/bin/with-contenv bash\nexec /usr/local/bin/start-deskclaw-webui\n" > /etc/s6-overlay/s6-rc.d/svc-deskclaw/run && \
    chmod +x /etc/s6-overlay/s6-rc.d/svc-deskclaw/run && \
    mkdir -p /etc/s6-overlay/s6-rc.d/svc-deskclaw/dependencies.d && \
    touch /etc/s6-overlay/s6-rc.d/svc-deskclaw/dependencies.d/init-adduser && \
    mkdir -p /etc/s6-overlay/s6-rc.d/user/contents.d && \
    touch /etc/s6-overlay/s6-rc.d/user/contents.d/svc-deskclaw

# -----------------------------------------------------------------------------
# 第十步: 安装 CodePilot
# -----------------------------------------------------------------------------
RUN wget -qO /tmp/CodePilot-amd64.deb https://github.com/op7418/CodePilot/releases/download/v0.49.0/CodePilot-0.49.0-amd64.deb && \
    apt-get install -y /tmp/CodePilot-amd64.deb && \
    rm -f /tmp/CodePilot-amd64.deb && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# 第十一步: 安装 Claude Code (采用 Seed Template 模式支持 /config 持久化)
# 痛点: Claude 的二进制和配置要求写在用户的 ~/.local 等相对目录内。
# 如果直接在构建时使用 root 安装，abc 用户运行时将无权执行或自更新。
# 如果在每次容器启动时重新下载，会阻塞启动阶段且无法离线。
# 方案: 在构建阶段安装至 /opt/claude-seed, 通过 s6 启动脚本动态映射到 /config
# -----------------------------------------------------------------------------
RUN mkdir -p /opt/claude-seed /custom-cont-init.d && \
    HOME=/opt/claude-seed bash -c "curl -fsSL https://claude.ai/install.sh | bash" && \
    printf "#!/bin/bash\n\
if [ ! -d /config/.local/share/claude ]; then\n\
  echo '>>> [Seed Template] 首次初始化 Claude Code 到 /config ...'\n\
  mkdir -p /config/.local/share /config/.local/bin\n\
  cp -a /opt/claude-seed/.local/share/claude /config/.local/share/\n\
  chown -R abc:abc /config/.local/share/claude\n\
  # 重建指向真实持久化路径的软链接\n\
  CLAUDE_VER=\$(ls /config/.local/share/claude/versions | head -n 1)\n\
  ln -sf /config/.local/share/claude/versions/\$CLAUDE_VER/claude /config/.local/bin/claude\n\
  chown -h abc:abc /config/.local/bin/claude\n\
fi\n\
# 确保终端包含 .local/bin (支持 bash/zsh)\n\
for rc in /config/.bashrc /config/.zshrc; do\n\
  if [ -f \$rc ] && ! grep -q '\.local/bin' \$rc 2>/dev/null; then\n\
    echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> \$rc\n\
  elif [ ! -f \$rc ]; then\n\
    echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' > \$rc\n\
    chown abc:abc \$rc\n\
  fi\n\
done\n" > /custom-cont-init.d/98-install-claude && \
    chmod +x /custom-cont-init.d/98-install-claude
# -----------------------------------------------------------------------------
# 元数据标签
# -----------------------------------------------------------------------------
LABEL maintainer="zhangjun" \
    description="webclaw KDE 桌面底包 - VSCode + Cursor + Antigravity + Chrome + JetBrains Mono + KDE 主题" \
    base="lscr.io/linuxserver/webtop:ubuntu-kde" \
    version="2.1.0"
