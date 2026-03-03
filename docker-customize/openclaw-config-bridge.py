import json
import os
import sys
from datetime import datetime

# =============================================================================
# zinoClaw Pro 环境变量配置桥接器 (v1.3.0)
# 精简版：仅保留核心模型、网关、记忆和浏览器配置
# =============================================================================

CONFIG_PATH = os.environ.get('OPENCLAW_CONFIG_PATH', '/config/.openclaw/openclaw.json')

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
                "plugins": {"entries": {}}
            }

        env = os.environ

        # --- 1. 模型提供商同步 (提供零配置默认值) ---
        p = ensure_path(config, ['models', 'providers', 'default'])
        
        # 基础凭据
        p['apiKey'] = env.get('API_KEY', 'sk-your-key-here')
        p['baseUrl'] = env.get('BASE_URL', 'https://api.openai.com/v1')
        p['api'] = env.get('API_PROTOCOL', 'openai-completions')
        
        # 模型列表解析 (支持逗号分隔)
        mid_raw = env.get('MODEL_ID', 'gpt-4o')
        m_ids = [x.strip() for x in mid_raw.split(',') if x.strip()]
        
        mlist = p.get('models', [])
        for m_id in m_ids:
            # 提取 ID (兼容 provider/id 格式)
            actual_id = m_id.split('/')[-1] if '/' in m_id else m_id
            m_obj = next((m for m in mlist if m.get('id') == actual_id), None)
            if not m_obj:
                m_obj = {"id": actual_id, "name": actual_id}
                mlist.append(m_obj)
            
            # 性能参数默认值
            m_obj["contextWindow"] = int(env.get('CONTEXT_WINDOW', 128000))
            m_obj["maxTokens"] = int(env.get('MAX_TOKENS', 4096))
        
        p['models'] = mlist
        
        # 设置主用模型引用
        primary_id = f"default/{actual_id}"
        ensure_path(config, ['agents', 'defaults', 'model'])['primary'] = primary_id
        print(f"✅ 模型提供商已确保: {primary_id}")


        # --- 2. 网关安全与认证 (强制同步，提供默认值) ---
        gw = ensure_path(config, ['gateway'])
        
        # 认证配置
        gw_token = env.get('OPENCLAW_GATEWAY_TOKEN', 'dev-token-123456')
        gw['auth'] = {"mode": "token", "token": gw_token}
        gw['bind'] = env.get('OPENCLAW_GATEWAY_BIND', 'lan')
        gw['port'] = int(env.get('OPENCLAW_GATEWAY_PORT', 18789))
        
        # 控制台 UI 安全配置
        cui = ensure_path(gw, ['controlUi'])
        cui['allowInsecureAuth'] = env.get('OPENCLAW_GATEWAY_ALLOW_INSECURE_AUTH', 'true').lower() == 'true'
        cui['dangerouslyAllowHostHeaderOriginFallback'] = True
        cui['dangerouslyDisableDeviceAuth'] = env.get('OPENCLAW_GATEWAY_DANGEROUSLY_DISABLE_DEVICE_AUTH', 'true').lower() == 'true'
        
        # 允许的域名 (默认包含 localhost 和 webtop 环境)
        origins_raw = env.get('OPENCLAW_GATEWAY_ALLOWED_ORIGINS', 'http://localhost')
        cui['allowedOrigins'] = [x.strip() for x in origins_raw.split(',') if x.strip()]


        # --- 3. 记忆与工作区增强 ---
        config['agents']['defaults']['workspace'] = "/config/.openclaw/workspace"
        memory = ensure_path(config, ['memory'])
        memory['backend'] = "qmd"
        qmd = ensure_path(memory, ['qmd'])
        qmd['command'] = "/usr/local/bin/qmd"
        qmd['paths'] = [{"path": "/config/.openclaw/workspace", "name": "workspace", "pattern": "**/*.md"}]

        # --- 4. 浏览器环境强制修正 ---
        browser = ensure_path(config, ['browser'])
        browser.update({"executablePath": "/usr/bin/chromium", "headless": True, "noSandbox": True})

        # --- 5. 最终保存 ---
        ensure_path(config, ['meta'])['lastTouchedAt'] = datetime.utcnow().isoformat() + 'Z'
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print("🚀 [Bridge] OpenClaw 核心配置同步完成")

    except Exception as e:
        print(f"❌ [Bridge] 同步失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    sync()
