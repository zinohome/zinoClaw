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
        is_first_run = not os.path.exists(CONFIG_PATH)
        env = os.environ
        
        if not is_first_run:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            print("🆕 [Bridge] 检测到首次启动，生成基础配置模板...")
            config = {
                "meta": {"lastTouchedVersion": "2026.3.2"},
                "agents": {"defaults": {"compaction": {"mode": "safeguard"}}},
                "gateway": {"mode": "local", "port": 18789, "bind": "lan"},
                "channels": {},
                "plugins": {"entries": {}}
            }

        # --- 1. 模型提供商同步 (绕过 "default" 关键字 Bug) ---
        provider_id = 'openai-proxy'
        has_model_env = any(k in env for k in ['API_KEY', 'BASE_URL', 'MODEL_ID'])
        if has_model_env or is_first_run:
            p = ensure_path(config, ['models', 'providers', provider_id])
            if 'API_KEY' in env: p['apiKey'] = env['API_KEY']
            elif is_first_run: p['apiKey'] = 'sk-your-key-here'
            
            if 'BASE_URL' in env: p['baseUrl'] = env['BASE_URL']
            elif is_first_run: p['baseUrl'] = 'https://api.openai.com/v1'
            
            p['api'] = env.get('API_PROTOCOL', p.get('api', 'openai-completions'))
            
            mid_raw = env.get('MODEL_ID', 'gpt-4o' if is_first_run else None)
            if mid_raw:
                m_ids = [x.strip() for x in mid_raw.split(',') if x.strip()]
                mlist = p.get('models', [])
                for m_id in m_ids:
                    actual_id = m_id.split('/')[-1] if '/' in m_id else m_id
                    m_obj = next((m for m in mlist if m.get('id') == actual_id), None)
                    if not m_obj:
                        m_obj = {"id": actual_id, "name": actual_id}
                        mlist.append(m_obj)
                    m_obj["contextWindow"] = int(env.get('CONTEXT_WINDOW', m_obj.get('contextWindow', 128000)))
                    m_obj["maxTokens"] = int(env.get('MAX_TOKENS', m_obj.get('maxTokens', 4096)))
                p['models'] = mlist
                primary_id = f"{provider_id}/{m_ids[0].split('/')[-1]}"
                ensure_path(config, ['agents', 'defaults', 'model'])['primary'] = primary_id
            print(f"✅ [Bridge] 模型路由已锁定到安全通道: {primary_id}")


        # --- 2. 网关安全与认证 (仅在环境变量存在或首次启动时应用) ---
        has_gw_env = any(k in env for k in ['OPENCLAW_GATEWAY_TOKEN', 'OPENCLAW_GATEWAY_BIND', 'OPENCLAW_GATEWAY_PORT'])
        if has_gw_env or is_first_run:
            gw = ensure_path(config, ['gateway'])
            
            if 'OPENCLAW_GATEWAY_TOKEN' in env or is_first_run:
                gw_token = env.get('OPENCLAW_GATEWAY_TOKEN', 'dev-token-123456' if is_first_run else None)
                if gw_token: gw['auth'] = {"mode": "token", "token": gw_token}
            
            gw['bind'] = env.get('OPENCLAW_GATEWAY_BIND', gw.get('bind', 'lan'))
            gw['port'] = int(env.get('OPENCLAW_GATEWAY_PORT', gw.get('port', 18789)))
            
            cui = ensure_path(gw, ['controlUi'])
            cui['allowInsecureAuth'] = env.get('OPENCLAW_GATEWAY_ALLOW_INSECURE_AUTH', 'true' if is_first_run else str(cui.get('allowInsecureAuth', 'true'))).lower() == 'true'
            cui['dangerouslyAllowHostHeaderOriginFallback'] = True
            cui['dangerouslyDisableDeviceAuth'] = env.get('OPENCLAW_GATEWAY_DANGEROUSLY_DISABLE_DEVICE_AUTH', 'true' if is_first_run else str(cui.get('dangerouslyDisableDeviceAuth', 'true'))).lower() == 'true'
            
            if 'OPENCLAW_GATEWAY_ALLOWED_ORIGINS' in env or is_first_run:
                origins_raw = env.get('OPENCLAW_GATEWAY_ALLOWED_ORIGINS', 'http://localhost' if is_first_run else None)
                if origins_raw: cui['allowedOrigins'] = [x.strip() for x in origins_raw.split(',') if x.strip()]
            print("✅ [Bridge] 网关配置已同步")

        # --- 3. 记忆与工作区增强 (核心路径通常是固定的) ---
        config['agents']['defaults']['workspace'] = "/config/.openclaw/workspace"
        memory = ensure_path(config, ['memory'])
        memory['backend'] = "qmd"
        qmd = ensure_path(memory, ['qmd'])
        qmd['command'] = "/usr/local/bin/qmd"
        qmd['paths'] = [{"path": "/config/.openclaw/workspace", "name": "workspace", "pattern": "**/*.md"}]

        # --- 4. 浏览器环境强制修正 (确保护箱即用，但不覆盖用户自定义) ---
        browser = ensure_path(config, ['browser'])
        if 'executablePath' not in browser:
            browser['executablePath'] = "/usr/bin/chromium"
        if 'headless' not in browser:
            browser['headless'] = True
        if 'noSandbox' not in browser:
            browser['noSandbox'] = True

        # --- 5. 最终保存 ---
        ensure_path(config, ['meta'])['lastTouchedAt'] = datetime.utcnow().isoformat() + 'Z'
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print("🚀 [Bridge] OpenClaw 配置同步流程执行完毕")


    except Exception as e:
        print(f"❌ [Bridge] 同步失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    sync()
