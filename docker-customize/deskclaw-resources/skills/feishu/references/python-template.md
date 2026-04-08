# 飞书 API Python 工具函数模板

以下模板可直接在 `exec` 中使用，复制后替换参数即可。

```python
import urllib.request, urllib.error, json, ssl

def feishu_api(app_id, app_secret):
    """返回一个封装好的飞书 API 调用器"""
    ctx = ssl.create_default_context()
    
    # 获取 token
    data = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, context=ctx) as resp:
        token = json.loads(resp.read())["tenant_access_token"]
    
    def call(method, path, body=None):
        url = f"https://open.feishu.cn/open-apis{path}"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
        req = urllib.request.Request(url, 
            data=json.dumps(body).encode() if body else None,
            headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, context=ctx) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return {"error": e.code, "body": e.read().decode()[:500]}
    
    return call

# 使用示例
api = feishu_api("cli_xxx", "secret_xxx")

# 发文本消息
api("POST", "/im/v1/messages?receive_id_type=open_id", {
    "receive_id": "ou_xxx",
    "msg_type": "text",
    "content": json.dumps({"text": "你好！"})
})

# 发卡片
api("POST", "/im/v1/messages?receive_id_type=open_id", {
    "receive_id": "ou_xxx",
    "msg_type": "interactive",
    "content": json.dumps({...})  # 卡片 JSON
})

# 添加文档权限
api("POST", "/drive/v1/permissions/DOC_ID/members?type=docx", {
    "member_type": "openid",
    "member_id": "ou_xxx",
    "perm": "full_access"
})
```
