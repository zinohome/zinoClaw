#!/bin/bash

# =========================================================================
# 芮通科技 AI 数字员工团队 — 本地与宿主机一键部署脚本
# =========================================================================

# 获取脚本所在目录的上一级（即 ReTone 目录），以便支持任意路径下执行脚本
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
RETONE_DIR="$(dirname "$SCRIPT_DIR")"

# 目标宿主的挂载根目录 (基于您的 docker volume 配置: /data/retone/config:/config)
TARGET_DIR="/data/retone/config/.openclaw"

echo "开始部署 OpenClaw 多智能体配置到: $TARGET_DIR"

# 1. 一键创建所有角色的独立记忆工作区目录
echo ">>> 创建 9 个独立的工作区目录..."
mkdir -p "$TARGET_DIR"/{workspace,dev-lead-workspace,dev-pm-workspace,dev-eng-workspace,dev-qa-workspace,res-lead-workspace,res-deep-workspace,res-insight-workspace,res-write-workspace}

# 2. 复制核心配置文件 (这里使用已经在 zinoClaw 目录下改好的 openclaw.json)
echo ">>> 同步全局核心路由配置文件 openclaw.json..."
cp "$RETONE_DIR/config/openclaw.json" "$TARGET_DIR/openclaw.json"

# 3. 为每个角色分发性格档案 (IDENTITY.md)
echo ">>> 发放各角色的独有身份系统 (IDENTITY.md)..."
cp "$RETONE_DIR/workspaces/shared/IDENTITY.md" "$TARGET_DIR/workspace/IDENTITY.md"
cp "$RETONE_DIR/workspaces/dev-team/open-lead/IDENTITY.md" "$TARGET_DIR/dev-lead-workspace/IDENTITY.md"
cp "$RETONE_DIR/workspaces/dev-team/open-pm/IDENTITY.md" "$TARGET_DIR/dev-pm-workspace/IDENTITY.md"
cp "$RETONE_DIR/workspaces/dev-team/open-dev/IDENTITY.md" "$TARGET_DIR/dev-eng-workspace/IDENTITY.md"
cp "$RETONE_DIR/workspaces/dev-team/open-qa/IDENTITY.md" "$TARGET_DIR/dev-qa-workspace/IDENTITY.md"
cp "$RETONE_DIR/workspaces/research-team/bo-lead/IDENTITY.md" "$TARGET_DIR/res-lead-workspace/IDENTITY.md"
cp "$RETONE_DIR/workspaces/research-team/bo-deep/IDENTITY.md" "$TARGET_DIR/res-deep-workspace/IDENTITY.md"
cp "$RETONE_DIR/workspaces/research-team/bo-insight/IDENTITY.md" "$TARGET_DIR/res-insight-workspace/IDENTITY.md"
cp "$RETONE_DIR/workspaces/research-team/bo-write/IDENTITY.md" "$TARGET_DIR/res-write-workspace/IDENTITY.md"

# 4. 用循环为所有人统一下发统一的灵魂骨架 (防止群聊回音壁的强制设定)
echo ">>> 下发企业统一工作准则 (SOUL.md)..."
for w_dir in workspace dev-lead-workspace dev-pm-workspace dev-eng-workspace dev-qa-workspace res-lead-workspace res-deep-workspace res-insight-workspace res-write-workspace; do
  cp "$RETONE_DIR/org/SOUL_TEMPLATE.md" "$TARGET_DIR/$w_dir/SOUL.md"
done

# 5. [强烈建议] 设置权限，避免 Docker 内的用户 (比如 1000/abc) 读写配置文件时遭受 Permission Denied
echo ">>> 修复目录权限 (777) 以适应 Docker 映射..."
chmod -R 777 "$TARGET_DIR"

echo "========================================================================="
echo "✅ 部署圆满成功！"
echo "✅ 所有 Token、身份设定、群聊防风墙已就绪。"
echo "✅ 您现在可以执行: docker compose up -d webclaw 唤醒您的全体员工了！"
echo "========================================================================="
