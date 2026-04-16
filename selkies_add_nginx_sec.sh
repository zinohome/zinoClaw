#!/bin/bash
# ==============================================================================
# Zino VDI Security Hotfix Patch [v1.1]
# Purpose: Add Nginx Basic Authentication to existing deployment
# Author: IBM Senior Application Architect (Persona)
# ==============================================================================
set -e

# [Phase 1] 权限与依赖校验
if [ "$EUID" -ne 0 ]; then
  echo "[-] Error: 该补丁涉及系统配置，请使用 root 权限执行！"
  exit 1
fi

echo "[*] Starting Security Patch ZINO-VDI-SEC-01..."

# [Phase 2] 组件安装
echo "[*] Step 1/5: 安装凭证生成工具..."
apt-get update -qq && apt-get install -y apache2-utils -qq

# [Phase 3] 凭证持久化
echo "[*] Step 2/5: 初始化网关凭据 (User: zhangjun)..."
# 使用 -b 模式以非交互方式创建文件
htpasswd -bc /etc/nginx/.htpasswd zhangjun passw0rd

# [Phase 4] Nginx 配置热注入
NGINX_CONF="/etc/nginx/sites-available/selkies"
BACKUP_CONF="/etc/nginx/sites-available/selkies.bak.$(date +%F_%H%M%S)"

echo "[*] Step 3/5: 备份并注入配置..."
if [ -f "$NGINX_CONF" ]; then
    cp "$NGINX_CONF" "$BACKUP_CONF"
    echo "    - 备份已创建: $BACKUP_CONF"
    
    # 使用 sed 在 ssl_certificate_key 匹配行后注入鉴权指令
    # 这样可以确保配置位于 server 块内的头部
    if ! grep -q "auth_basic" "$NGINX_CONF"; then
        sed -i '/ssl_certificate_key/a \    # Gateway Authentication Added by Architect Patch\n    auth_basic "Zino VDI Restricted Access";\n    auth_basic_user_file /etc/nginx/.htpasswd;' "$NGINX_CONF"
        echo "    - 鉴权指令注入成功。"
    else
        echo "    - 检测到已存在鉴权指令，跳过注入。"
    fi
else
    echo "[-] Error: 未找到 Nginx 配置文件 $NGINX_CONF，补丁终止。"
    exit 1
fi

# [Phase 5] 语法校准与激活
echo "[*] Step 4/5: 校验 Nginx 拓扑..."
if nginx -t; then
    echo "[*] Step 5/5: 重载网关引擎..."
    systemctl reload nginx
    echo "================================================================"
    echo " [OK] 补丁升级成功！"
    echo " 现在访问 VDI 将被强制要求输入身份凭证。"
    echo " 鉴权凭证: zhangjun / passw0rd"
    echo "================================================================"
else
    echo "[-] Error: 配置语法校验异常，正在回滚..."
    cp "$BACKUP_CONF" "$NGINX_CONF"
    systemctl reload nginx
    echo "[!] 补丁已回滚，请检查配置兼容性。"
    exit 1
fi
