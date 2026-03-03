# =============================================================================
# OpenClaw 定制 KDE 桌面镜像
# 基础镜像: linuxserver/webtop:zino-kde (私有 Harbor)
# 功能:
#   1. 安装 Ubuntu 常用基础命令工具
#   2. 安装 JetBrains Mono 字体（字体文件，不做 KDE 配置，桌面自行设置）
#   3. 安装 KDE Plasma Look-and-Feel 主题包
# 构建命令:
#   docker build -t harbor.naivehero.top:8443/baseimages/linuxserver/webtop:zino-kde-custom .
# =============================================================================

FROM harbor.naivehero.top:8443/baseimages/linuxserver/webtop:zino-kde

# -----------------------------------------------------------------------------
# 第零步: 替换 apt 源为清华大学镜像，并全量更新系统软件包
# 使用清华源加速国内构建，避免访问境外源超时
# apt dist-upgrade 比 apt upgrade 更彻底，可处理依赖关系变化的包
# 注意: 使用 printf 逐行写入，避免 heredoc 被 Dockerfile linter 误判
# -----------------------------------------------------------------------------

# 备份原始 sources.list 并替换为清华镜像源（Ubuntu 24.04 Noble）
RUN printf '%s\n' \
    '# 清华大学开源软件镜像站 - Ubuntu 24.04 Noble' \
    '# 默认注释了源码镜像以提高 apt update 速度' \
    'deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ noble main restricted universe multiverse' \
    '# deb-src https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ noble main restricted universe multiverse' \
    'deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ noble-updates main restricted universe multiverse' \
    '# deb-src https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ noble-updates main restricted universe multiverse' \
    'deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ noble-backports main restricted universe multiverse' \
    '# deb-src https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ noble-backports main restricted universe multiverse' \
    'deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ noble-security main restricted universe multiverse' \
    '# deb-src https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ noble-security main restricted universe multiverse' \
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
# 使用单个 RUN 指令合并操作，减少镜像层数
# 安装后清理 apt 缓存，控制镜像体积
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
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# 第二步: 安装 JetBrains Mono 字体
# 字体文件复制到 /usr/share/fonts/truetype/JetBrainsMono/ (系统级字体目录)
# fc-cache -fv 刷新字体缓存，使字体全局生效
# -----------------------------------------------------------------------------

# 将本地字体目录复制到镜像内
COPY docker-customize/Fonts/JetBrainsMono/ /usr/share/fonts/truetype/JetBrainsMono/

# 刷新字体缓存
RUN fc-cache -fv

# -----------------------------------------------------------------------------
# 第三步: 安装 KDE Plasma Look-and-Feel 主题
# 这四个主题包均为 KDE Global Theme (look-and-feel)，
# 标准安装目录为 /usr/share/plasma/look-and-feel/
#
# 包含的主题:
#   - com.github.varlesh.greybird   (Greybird KDE Look-and-Feel)
#   - com.github.varlesh.materia-dark (Materia Dark KDE Look-and-Feel)
#   - com.github.varlesh.rounded    (Rounded KDE Look-and-Feel)
#   - ExposeAir                     (ExposeAir Global Theme)
# -----------------------------------------------------------------------------
COPY docker-customize/Themes/ /tmp/themes/

RUN set -eux; \
    # 确保目标目录存在
    mkdir -p /usr/share/plasma/look-and-feel/; \
    \
    # 解压三个 .tar.gz 主题包
    for pkg in \
    com.github.varlesh.greybird.tar.gz \
    com.github.varlesh.materia-dark.tar.gz \
    com.github.varlesh.rounded.tar.gz; \
    do \
    echo ">>> 安装主题: $pkg"; \
    tar -xzf /tmp/themes/$pkg -C /usr/share/plasma/look-and-feel/; \
    done; \
    \
    # 解压 .tar.xz 主题包 (ExposeAir)
    echo ">>> 安装主题: exposeair-global-30.tar.xz"; \
    tar -xJf /tmp/themes/exposeair-global-30.tar.xz -C /usr/share/plasma/look-and-feel/; \
    \
    # 清理临时文件
    rm -rf /tmp/themes; \
    \
    # 验证主题已安装 (打印目录列表用于构建日志确认)
    echo ">>> 已安装的 KDE 主题:"; \
    ls -la /usr/share/plasma/look-and-feel/

# -----------------------------------------------------------------------------
# 元数据标签
# -----------------------------------------------------------------------------
LABEL maintainer="zhangjun" \
    description="OpenClaw KDE 定制桌面 - 含 JetBrains Mono 字体 + 自定义主题" \
    base="linuxserver/webtop:zino-kde" \
    version="1.0.0"
