#!/usr/bin/env python3
"""
B站分步登录脚本
用法: 
  python3 bili_login_step.py qrcode    # 生成二维码
  python3 bili_login_step.py check     # 检查扫码状态并保存凭据
"""

import asyncio
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
SKILL_DIR = SCRIPT_DIR.parent
DATA_DIR = SKILL_DIR / "data"
QR_CODE_FILE = DATA_DIR / "qrcode.png"
QR_KEY_FILE = DATA_DIR / "qrcode_key.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)

import credential_store


async def generate_qrcode():
    """生成二维码"""
    from bilibili_api.login_v2 import QrCodeLogin
    
    print("📱 正在生成登录二维码...")
    
    login = QrCodeLogin()
    await login.generate_qrcode()
    
    # 保存二维码图片
    qr_pic = login.get_qrcode_picture()
    qr_pic.to_file(str(QR_CODE_FILE))
    print(f"✅ 二维码已保存到: {QR_CODE_FILE}")
    
    # 保存登录实例的内部状态（qr_key）
    qr_key_data = {
        'qr_key': login._QrCodeLogin__qr_key
    }
    with open(QR_KEY_FILE, 'w') as f:
        json.dump(qr_key_data, f)
    
    print("")
    print("🔍 请用哔哩哔哩 App 扫描二维码")
    print(f"   二维码路径: {QR_CODE_FILE}")
    print("")
    print("扫码完成后，运行: python3 bili_login_step.py check")
    
    return True


async def check_and_save():
    """检查扫码状态并保存凭据"""
    from bilibili_api.login_v2 import QrCodeLogin, QrCodeLoginEvents
    
    # 读取之前保存的 qrcode_key
    if not QR_KEY_FILE.exists():
        print("❌ 未找到二维码信息，请先运行: python3 bili_login_step.py qrcode")
        return False
    
    with open(QR_KEY_FILE, 'r') as f:
        qr_key_data = json.load(f)
    
    qr_key = qr_key_data.get('qr_key')
    if not qr_key:
        print("❌ 二维码信息无效，请重新生成")
        return False
    
    print(f"🔍 检查扫码状态...")
    
    # 创建新的登录实例并设置 qr_key
    login = QrCodeLogin()
    login._QrCodeLogin__qr_key = qr_key
    
    # 检查状态
    try:
        events = await login.check_state()
        
        if events == QrCodeLoginEvents.SCAN:
            print("📲 已扫描，请在手机上点击确认...")
            print("确认后再次运行: python3 bili_login_step.py check")
            return False
        elif events == QrCodeLoginEvents.CONF:
            print("✅ 已确认，正在获取凭据...")
        elif events == QrCodeLoginEvents.TIMEOUT:
            print("❌ 二维码已过期，请重新生成")
            return False
        
        if login.has_done():
            credential = login.get_credential()
            data = {
                'sessdata': credential.sessdata,
                'bili_jct': credential.bili_jct,
                'buvid3': credential.buvid3,
                'dedeuserid': credential.dedeuserid,
                'ac_time_value': credential.ac_time_value,
            }
            credential_store.save(data)
            print("🎉 登录成功！凭据已加密保存")
            return True
        else:
            print("⏳ 等待扫码中...")
            print("扫码后再次运行: python3 bili_login_step.py check")
            return False
            
    except Exception as e:
        print(f"❌ 检查状态出错: {e}")
        return False


async def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 bili_login_step.py qrcode  # 生成二维码")
        print("  python3 bili_login_step.py check   # 检查扫码状态")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == 'qrcode':
        await generate_qrcode()
    elif cmd == 'check':
        await check_and_save()
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
