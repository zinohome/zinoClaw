#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"

echo "📦 安装 B站 MCP 依赖..."
echo ""

# ============================================
# 1. 检查 Python 版本
# ============================================
echo "🔍 检查 Python 环境..."

if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3.9+"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
REQUIRED_VERSION="3.9"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ 需要 Python >= 3.9，当前版本: $PYTHON_VERSION"
    exit 1
fi

echo "✅ Python 版本: $PYTHON_VERSION"

# ============================================
# 2. 安装 Python 依赖
# ============================================
echo ""
echo "📥 安装 Python 依赖..."

pip3 install -r "$SKILL_DIR/requirements.txt" -q

echo "✅ Python 依赖安装完成"

# ============================================
# 3. 检查可选依赖 - ffmpeg
# ============================================
echo ""
echo "🔍 检查可选依赖..."

FFMPEG_AVAILABLE=false
if command -v ffmpeg &> /dev/null; then
    FFMPEG_VERSION=$(ffmpeg -version 2>&1 | head -n1 | awk '{print $3}')
    echo "✅ ffmpeg 已安装 (版本: $FFMPEG_VERSION)"
    FFMPEG_AVAILABLE=true
else
    echo "⚠️  ffmpeg 未安装"
    echo "   ffmpeg 用于视频处理（提取封面、压缩等）"
    echo "   没有 ffmpeg 时会使用 OpenCV 作为降级方案"
    echo ""
    echo "   安装方法："
    echo "   - macOS:   brew install ffmpeg"
    echo "   - Ubuntu:  sudo apt install ffmpeg"
    echo "   - Windows: choco install ffmpeg"
fi

# ============================================
# 4. 检查 OpenCV（降级方案）
# ============================================
OPENCV_AVAILABLE=false
if python3 -c "import cv2" 2>/dev/null; then
    OPENCV_VERSION=$(python3 -c "import cv2; print(cv2.__version__)")
    echo "✅ OpenCV 已安装 (版本: $OPENCV_VERSION)"
    OPENCV_AVAILABLE=true
else
    echo "⚠️  OpenCV 未安装（已在依赖中包含，应该会自动安装）"
fi

# ============================================
# 5. 创建数据目录
# ============================================
echo ""
DATA_DIR="$SKILL_DIR/data"
mkdir -p "$DATA_DIR"
echo "✅ 数据目录已创建: $DATA_DIR"

# ============================================
# 6. 总结
# ============================================
echo ""
echo "============================================"
echo "🎉 安装完成！"
echo "============================================"
echo ""
echo "📍 凭据存储位置: $DATA_DIR/credential.json"
echo ""
echo "📋 功能状态："
if [ "$FFMPEG_AVAILABLE" = true ]; then
    echo "   ✅ 视频封面提取: ffmpeg (推荐)"
elif [ "$OPENCV_AVAILABLE" = true ]; then
    echo "   ✅ 视频封面提取: OpenCV (降级方案)"
else
    echo "   ❌ 视频封面提取: 不可用，请安装 ffmpeg 或确保 OpenCV 正确安装"
fi
echo ""
echo "💡 首次使用请运行登录脚本："
echo "   python3 $SCRIPT_DIR/bili_login_step.py qrcode"
echo ""
