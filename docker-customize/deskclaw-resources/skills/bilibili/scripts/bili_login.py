#!/usr/bin/env python3
"""
B站扫码登录脚本
用法: python3 bili_login.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
SKILL_DIR = SCRIPT_DIR.parent
DATA_DIR = SKILL_DIR / "data"
QR_CODE_FILE = DATA_DIR / "qrcode.png"

DATA_DIR.mkdir(parents=True, exist_ok=True)

import credential_store


async def login():
    """扫码登录"""
    try:
        from bilibili_api.login_v2 import QrCodeLogin, QrCodeLoginEvents
        
        print("📱 正在生成登录二维码...")
        
        # 创建登录实例
        login_instance = QrCodeLogin()
        await login_instance.generate_qrcode()
        
        # 保存二维码图片
        qr_pic = login_instance.get_qrcode_picture()
        qr_pic.to_file(str(QR_CODE_FILE))
        
        print(f"✅ 二维码已保存到: {QR_CODE_FILE}")
        print("")
        print("🔍 请用哔哩哔哩 App 扫描二维码登录")
        print("   （也可以在终端显示二维码）")
        print("")
        
        # 在终端显示二维码
        try:
            qr_terminal = login_instance.get_qrcode_terminal()
            print(qr_terminal)
        except:
            pass
        
        print("")
        print("⏳ 等待扫码...")
        
        # 轮询检查状态
        while True:
            await asyncio.sleep(2)
            
            try:
                events = await login_instance.check_state()
                
                if events == QrCodeLoginEvents.SCAN:
                    print("📲 已扫描，请在手机上确认...")
                elif events == QrCodeLoginEvents.CONF:
                    print("✅ 已确认，正在获取凭据...")
                elif events == QrCodeLoginEvents.TIMEOUT:
                    print("❌ 二维码已过期，请重新运行脚本")
                    return False
                
                if login_instance.has_done():
                    credential = login_instance.get_credential()
                    data = {
                        'sessdata': credential.sessdata,
                        'bili_jct': credential.bili_jct,
                        'buvid3': credential.buvid3,
                        'dedeuserid': credential.dedeuserid,
                        'ac_time_value': credential.ac_time_value,
                    }
                    credential_store.save(data)
                    print("")
                    print("🎉 登录成功！凭据已加密保存")
                    return True
                    
            except Exception as e:
                print(f"检查状态出错: {e}")
                await asyncio.sleep(3)
                
    except Exception as e:
        print(f"❌ 登录失败: {e}")
        return False


if __name__ == '__main__':
    result = asyncio.run(login())
    sys.exit(0 if result else 1)
