import json
import os
import sys
from datetime import datetime

# =============================================================================
# zinoClaw Pro 环境变量配置桥接器 (v1.2.2)
# 集成插件安装路径管理
# =============================================================================

CONFIG_PATH = os.environ.get('OPENCLAW_CONFIG_PATH', '/config/.openclaw/openclaw.json')
EXT_BASE = "/config/.openclaw/extensions"

def ensure_path(cfg, keys):
    curr = cfg
    for k in keys:
        if k not in curr: curr[k] = {}
        curr = curr[k]
    return curr

def sync():
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {
                "meta": {"lastTouchedVersion": "2026.3.2"},
                "agents": {"defaults": {"compaction": {"mode": "safeguard"}}},
                "gateway": {"mode": "local", "port": 18789, "bind": "lan"},
                "channels": {},
                "plugins": {"entries": {}, "installs": {}}
            }

        env = os.environ

        # --- 1. 模型提供商同步 ---
        if env.get('API_KEY') and env.get('BASE_URL'):
            p = ensure_path(config, ['models', 'providers', 'default'])
            p['apiKey'] = env['API_KEY']
            p['baseUrl'] = env['BASE_URL']
            p['api'] = env.get('API_PROTOCOL', 'openai-completions')
            
            mid_raw = env.get('MODEL_ID', 'gpt-4o')
            m_ids = [x.strip() for x in mid_raw.split(',') if x.strip()]
            
            mlist = p.get('models', [])
            for m_id in m_ids:
                actual_id = m_id.split('/')[-1] if '/' in m_id else m_id
                m_obj = next((m for m in mlist if m.get('id') == actual_id), None)
                if not m_obj:
                    m_obj = {"id": actual_id, "name": actual_id}
                    mlist.append(m_obj)
                m_obj["contextWindow"] = int(env.get('CONTEXT_WINDOW', 200000))
                m_obj["maxTokens"] = int(env.get('MAX_TOKENS', 8192))
            
            p['models'] = mlist
            primary_id = f"default/{m_ids[0]}" if '/' not in m_ids[0] else m_ids[0]
            ensure_path(config, ['agents', 'defaults', 'model'])['primary'] = primary_id
            print(f"✅ 模型已同步: {primary_id}")

        # --- 2. 网关安全与认证 ---
        if env.get('OPENCLAW_GATEWAY_TOKEN'):
            gw = ensure_path(config, ['gateway'])
            gw['auth'] = {"mode": "token", "token": env['OPENCLAW_GATEWAY_TOKEN']}
            gw['bind'] = env.get('OPENCLAW_GATEWAY_BIND', 'lan')
            gw['port'] = int(env.get('OPENCLAW_GATEWAY_PORT', 18789))
            
            cui = ensure_path(gw, ['controlUi'])
            cui['allowInsecureAuth'] = env.get('OPENCLAW_GATEWAY_ALLOW_INSECURE_AUTH', 'true').lower() == 'true'
            cui['dangerouslyAllowHostHeaderOriginFallback'] = True
            cui['dangerouslyDisableDeviceAuth'] = env.get('OPENCLAW_GATEWAY_DANGEROUSLY_DISABLE_DEVICE_AUTH', 'true').lower() == 'true'

        # --- 3. IM 渠道与插件自动激活 ---
        channels = ensure_path(config, ['channels'])
        plugins = ensure_path(config, ['plugins'])
        entries = ensure_path(plugins, ['entries'])
        installs = ensure_path(plugins, ['installs'])
        
        def register_plugin(cid, source_type, spec):
            entries[cid] = {"enabled": True}
            if cid not in installs:
                installs[cid] = {
                    "source": source_type,
                    "spec": spec,
                    "installPath": f"{EXT_BASE}/{cid}",
                    "installedAt": datetime.utcnow().isoformat() + 'Z'
                }

        # 飞书
        if env.get('FEISHU_APP_ID') and env.get('FEISHU_APP_SECRET'):
            fs = ensure_path(channels, ['feishu'])
            fs.update({"enabled": True, "dmPolicy": "pairing", "groupPolicy": "open"})
            acc = ensure_path(fs, ['accounts', 'main'])
            acc.update({"appId": env['FEISHU_APP_ID'], "appSecret": env['FEISHU_APP_SECRET']})
            register_plugin('feishu', 'npm', '@openclaw/feishu')
            print("✅ 飞书渠道已激活")

        # 钉钉
        if env.get('DINGTALK_CLIENT_ID') and env.get('DINGTALK_CLIENT_SECRET'):
            dt = ensure_path(channels, ['dingtalk'])
            dt.update({"enabled": True, "clientId": env['DINGTALK_CLIENT_ID'], "clientSecret": env['DINGTALK_CLIENT_SECRET']})
            register_plugin('dingtalk', 'path', f"{EXT_BASE}/dingtalk")
            print("✅ 钉钉渠道已激活")
        
        # 企业微信
        if env.get('WECOM_TOKEN') and env.get('WECOM_ENCODING_AES_KEY'):
            wc = ensure_path(channels, ['wecom'])
            wc.update({"enabled": True, "token": env['WECOM_TOKEN'], "encodingAesKey": env['WECOM_ENCODING_AES_KEY']})
            register_plugin('wecom', 'npm', '@sunnoy/wecom')
            print("✅ 企业微信渠道已激活")
            
        # NapCat (QQ)
        if env.get('NAPCAT_REVERSE_WS_PORT'):
            nc = ensure_path(channels, ['napcat'])
            nc.update({"enabled": True, "reverseWsPort": int(env['NAPCAT_REVERSE_WS_PORT'])})
            register_plugin('napcat', 'path', f"{EXT_BASE}/napcat")
            print("✅ NapCat (QQ) 渠道已激活")

        # --- 4. 记忆与工作区增强 ---
        memory = ensure_path(config, ['memory'])
        memory['backend'] = "qmd"
        qmd = ensure_path(memory, ['qmd'])
        qmd['command'] = "/usr/local/bin/qmd"
        qmd['paths'] = [{"path": "/config/.openclaw/workspace", "name": "workspace", "pattern": "**/*.md"}]

        # --- 5. 浏览器环境强制修正 ---
        browser = ensure_path(config, ['browser'])
        browser.update({"executablePath": "/usr/bin/chromium", "headless": True, "noSandbox": True})

        # --- 6. 最终保存 ---
        ensure_path(config, ['meta'])['lastTouchedAt'] = datetime.utcnow().isoformat() + 'Z'
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print("🚀 [Bridge] OpenClaw 增强配置同步完成")

    except Exception as e:
        print(f"❌ [Bridge] 同步失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    sync()
