#!/bin/bash
# ==============================================================================
# Zino VDI One-Click Enterprise Deployment Script
# Architecture: IBM Component Business Model (CBM) Aligned
# Components: Xorg-Dummy, PulseAudio, Nginx SSL, Python WebRTC, FileBrowser
# ==============================================================================
set -e

# [Phase 0] 基础守护与执行流校验
if [ "$EUID" -ne 0 ]; then
  echo "[Error] 入口被拒绝。由于涉及 Systemd 与内核重构，请使用 root 权限执行此剧本！"
  exit
fi

echo "================================================================"
echo "    ZINO CLAW Enterprise VDI - Automated Deployment Architect   "
echo "================================================================"

export VDI_USER="ubuntu"
export OPT_DIR="/opt"
export SELKIES_CORE="$OPT_DIR/selkies-core"
export SELKIES_WEB="$OPT_DIR/selkies-web/selkies-dashboard"

echo "[Phase 1] 底盘加固: 依赖环境夯实与守护程序包下发..."
apt-get update
# 核心依赖：Xorg虚拟环境，Pulse音轨，反向路由Nginx，Python底座构建包等
apt-get install -y xserver-xorg-video-dummy pulseaudio nginx python3-pip curl jq dbus-x11 pkg-config libcairo2-dev libgirepository1.0-dev pciutils

echo "[Phase 2] 安全脱水: 破坏性系统瘦身与娱乐残留剥离..."
# 锚定核心，防止雪崩
apt-mark manual plasma-desktop plasma-workspace xfce4-session kwin-x11 2>/dev/null || true
# 暴力绞杀巨石办公组件与内置消遣环境
apt-get remove -y --purge "libreoffice*" ure uno-libs-private 2>/dev/null || true
for app in kpat kmines ksudoku kmahjongg kshisen kreversi kblocks ktuberling bovo klines knetwalk picmi aisleriot gnome-mahjongg gnome-mines gnome-sudoku kdeconnect konversation neochat elisa elisa-player haruna xfburn; do
    apt-get remove -y --purge $app 2>/dev/null || true
done
apt-get autoremove -y --purge
apt-get clean
rm -rf /usr/share/applications/libreoffice*.desktop

echo "[Phase 3] 伪装驱动: 注入 Xorg-Dummy 显卡物理虚拟化层 (解决自适应分辨率撕裂)..."
cat > /etc/X11/xorg-dummy.conf << 'EOF'
Section "Device"
    Identifier  "Configured Video Device"
    Driver      "dummy"
    VideoRam    256000
EndSection
Section "Monitor"
    Identifier  "Configured Monitor"
    HorizSync   31.5 - 133.0
    VertRefresh 50.0 - 120.0
EndSection
Section "Screen"
    Identifier  "Default Screen"
    Monitor     "Configured Monitor"
    Device      "Configured Video Device"
    DefaultDepth 24
    SubSection "Display"
        Depth 24
        Modes "1920x1080" "1280x720"
    EndSubSection
EndSection
EOF
echo "allowed_users=anybody" > /etc/X11/Xwrapper.config


echo "[Phase 4] 核心层: 重构 Selkies 音视频流转引擎启动链..."
cat > $SELKIES_CORE/start_selkies.sh << 'EOF_SCRIPT'
#!/bin/bash
export DISPLAY=:99
export PULSE_SERVER=unix:/tmp/pulseaudio.socket
export XDG_RUNTIME_DIR=/tmp/runtime-ubuntu
export HOME=/home/ubuntu
export USER=ubuntu

# 硬核垃圾销毁与沙盒边界划分
rm -rf /tmp/.X99-lock /tmp/.X11-unix/X99 /tmp/pulseaudio.socket /tmp/pulse-* /tmp/selkies_*
mkdir -p /tmp/runtime-ubuntu /home/ubuntu/Downloads /home/ubuntu/Desktop
chmod 0700 /tmp/runtime-ubuntu

# 冷启动原生虚拟硬件驱动
Xorg -noreset +extension GLX +extension RANDR +extension RENDER -logfile /tmp/xorg.log -config /etc/X11/xorg-dummy.conf :99 &
sleep 2

# 打通音频底座并设立输出陷阱点 (Null-Sink)
pulseaudio -D --exit-idle-time=-1 -n \
  --load="module-native-protocol-unix auth-anonymous=1 socket=/tmp/pulseaudio.socket" \
  --load="module-null-sink sink_name=output"
pactl set-default-sink output

# 桌面环境动态路由分发 (Dynamic Desktop Router)
DESKTOP_ENV=$(cat /desktop_env 2>/dev/null || echo "kde")
DESKTOP_ENV=$(echo "$DESKTOP_ENV" | tr -d '[:space:]')
if [ "$DESKTOP_ENV" = "xfce" ]; then
    LIBGL_ALWAYS_SOFTWARE=1 xfce4-session > /tmp/desktop.log 2>&1 &
else
    LIBGL_ALWAYS_SOFTWARE=1 startplasma-x11 > /tmp/desktop.log 2>&1 &
fi

sleep 3
# 激活 WebRTC 视频与指令混传中枢，屏蔽原始前端内置控件显示权
cd /opt/selkies-core
python3 -m selkies \
    --encoder="x264enc" \
    --port=8082 \
    --mode="websockets" \
    --audio_device_name="output.monitor" \
    --h264_streaming_mode=true \
    --ui_sidebar_show_files=false \
    --ui_sidebar_show_apps=false \
    --ui_sidebar_show_sharing=false \
    --ui_sidebar_show_gamepads=false
EOF_SCRIPT
chmod +x $SELKIES_CORE/start_selkies.sh


echo "[Phase 5] 视图层: Vue/React 前台暗网结界掩埋 (UI Cloaking & Mocking)..."
mkdir -p $SELKIES_WEB/src/
# 空投镇定剂假体，切断 WebRTC 前端崩溃红屏路径
echo "console.log('Dummy Gamepad Locked');window.universalTouchGamepad = {};" > $SELKIES_WEB/src/universalTouchGamepad.js
echo "console.log('Dummy TouchMouse Locked');window.touchMouse = {};" > $SELKIES_WEB/src/touchMouse.js
chown -R $VDI_USER:$VDI_USER $SELKIES_WEB

# 强行给入口页埋入 DOM 隐身级指令，彻底遮盖原生侧边栏残渣
find /opt/selkies-web -name index.html | while read WEB_INDEX; do
    sed -i '/zino-ui-tweak/d' "$WEB_INDEX"
    sed -i '/<\/head>/i \  <style id="zino-ui-tweak">[title*="App"], [title*="Shar"], [title*="Game"], [title*="File"], [title*="应用"], [title*="共享"], [title*="手柄"], [title*="文件"], [aria-label*="App"], [aria-label*="Shar"], [aria-label*="Game"], [aria-label*="File"], [aria-label*="应用"], [aria-label*="共享"], [aria-label*="手柄"], [aria-label*="文件"] { display: none !important; height: 0 !important; width: 0 !important; pointer-events: none !important; opacity: 0 !important; margin: 0 !important; padding: 0 !important; }</style>' "$WEB_INDEX"
done


echo "[Phase 6] 数据引擎: 外部剥离私有云系统 FileBrowser 部署 (解耦设计)..."
curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash
rm -f /home/$VDI_USER/filebrowser.db
filebrowser -d /home/$VDI_USER/filebrowser.db config init || true
# 控制面发放权柄：生成高防初始鉴权锁
filebrowser -d /home/$VDI_USER/filebrowser.db users add zhangjun passw0rd --perm.admin || true
chown $VDI_USER:$VDI_USER /home/$VDI_USER/filebrowser.db*

cat > /etc/systemd/system/zino-files.service << 'EOF'
[Unit]
Description=Zino VDI File Manager (Microservice)

[Service]
User=ubuntu
ExecStart=/usr/local/bin/filebrowser -r /home/ubuntu -p 8084 -a 127.0.0.1 -d /home/ubuntu/filebrowser.db -b /filebrowser
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF


echo "[Phase 7] 发射控制: 注册 VDI 系统级自动守护神进程..."
cat > /etc/systemd/system/selkies-vdi.service << 'EOF'
[Unit]
Description=Zino Selkies VDI Engine
After=network.target nginx.service

[Service]
User=ubuntu
Environment="HOME=/home/ubuntu"
Environment="USER=ubuntu"
WorkingDirectory=/opt/selkies-core
ExecStart=/opt/selkies-core/start_selkies.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF


echo "[Phase 8] 总网关: 重新铸造 Nginx 全局反向路由隧道..."
# 为 3000 端口加密通道生成自托管前置证书
mkdir -p /etc/nginx/ssl
if [ ! -f /etc/nginx/ssl/vdi.crt ]; then
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/vdi.key -out /etc/nginx/ssl/vdi.crt \
    -subj "/C=CN/ST=Shanghai/L=Shanghai/O=Zino/OU=VDI/CN=zino"
fi

cat > /etc/nginx/sites-available/selkies << 'EOF'
server {
    listen 3000 ssl;
    server_name _;
    
    ssl_certificate /etc/nginx/ssl/vdi.crt;
    ssl_certificate_key /etc/nginx/ssl/vdi.key;

    # 主网关指向 Web 前端骨架
    root /opt/selkies-web/selkies-dashboard;
    index index.html index.htm;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # 路由劫持：将大文件分片传输全权丢给子系统端口 8084
    location /filebrowser {
        proxy_pass http://127.0.0.1:8084;
    }

    # 大动脉：贯穿 WebRTC 信令与高频帧的协议级长连接
    location /websocket {
        proxy_pass http://127.0.0.1:8082;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
EOF
ln -sf /etc/nginx/sites-available/selkies /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default


echo "[Finalizer] 重载核心中枢与点火收尾..."
systemctl daemon-reload
systemctl enable --now zino-files.service
systemctl enable --now selkies-vdi.service
systemctl restart nginx

echo "================================================================"
echo " [SUCCESS] Zino VDI 全装甲分离式企业架构底座已物理熔铸完毕！"
echo " "
echo " ▶ 无感 Web 极速控制台: https://<本机IP>:3000"
echo " ▶ 云生代 NAS 数据中心: https://<本机IP>:3000/filebrowser"
echo " ▶ [数据交互出厂凭证] : 账号 zhangjun / 秘论 passw0rd"
echo " "
echo " ▶ 极简动态软路由 (毫秒级切换轻甲兵):"
echo "   echo 'xfce' > /desktop_env && systemctl restart selkies-vdi"
echo "================================================================"
