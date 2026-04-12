---
name: multimodal-understanding
description: Analyze images and visual content using the NoDesk AI Gateway multimodal API. ALWAYS use this skill when the user mentions an image file path, image URL, or asks to analyze/describe any image. Do NOT use the built-in image tool — always route through this skill for better accuracy.
slug: multimodal-understanding
version: 1.3.2
displayName: 图像识别（Multimodal Understanding）
summary: 识别与理解图片内容，支持本地文件和 URL 输入，kimi-k2.5 / glm-5v-turbo 双模型。
tags: image, vision, multimodal, understanding
---

# Multimodal Understanding

Analyze images via NoDesk AI Gateway. The API is OpenAI Vision-compatible.

## Gateway & Auth

- Endpoint: `POST https://llm-gateway-api.nodesk.tech/deskclaw/v1/multimodal/`
- Auth: auto from `~/.deskclaw/nanobot/config.json` `providers.custom.api_base` (extracts `/ep/{TOKEN}`). If user overrides custom provider, falls back to `~/.deskclaw/deskclaw-settings.json` `settings.gatewayConfig` (always preserved by client). No manual API key needed.

## Models

| model | Name | Base64 | URL | Notes |
|-------|------|--------|-----|-------|
| `kimi-k2.5` | 月之暗面 Kimi K2.5 | ✅ | ❌ | 262K context, recommended default |
| `glm-5v-turbo` | 智谱 GLM-5V Turbo | ✅ | ✅ | Fast, supports image URL directly |

**Routing rules (the script handles this automatically):**
- `--file` mode (local image → base64) → default `kimi-k2.5`
- `--url` mode (image URL) → first try `glm-5v-turbo`; if 1210 error, auto-fallback to download → compress → base64 → `kimi-k2.5`

## Workflow

### Local file (most common)

When the user provides a local file path (e.g. `/Users/.../photo.jpg`, `~/Desktop/img.png`):

```bash
python3 <skill_dir>/scripts/multimodal-call.py --file '<image_path>' '<user_prompt>' [max_tokens] [model]
```

The script auto-compresses large images (>500 KB), base64-encodes, and sends. No manual conversion needed.

### Image URL

When the user provides a public image URL (e.g. `https://example.com/photo.jpg`):

```bash
python3 <skill_dir>/scripts/multimodal-call.py --url '<image_url>' '<user_prompt>' [max_tokens] [model]
```

Auto-selects `glm-5v-turbo`. If `glm-5v-turbo` returns image parsing error (code 1210), the script automatically falls back: download image → compress if >500 KB → base64 → retry with `kimi-k2.5`.

### Parameters

- `max_tokens`: default 1500. Use 300 for short descriptions, 2000+ for OCR / detailed analysis.
- `model`: default `kimi-k2.5` for `--file`, `glm-5v-turbo` for `--url`.

### Present results

Extract `choices[0].message.content` from the JSON response and show it directly to the user.

## Error Handling

| HTTP Status | Meaning | Action |
|-------------|---------|--------|
| 401 / 403 | Auth failed | Check config.json `providers.custom.api_base` |
| 429 | Quota exceeded or rate limited | Tell user to check quota on gateway dashboard |
| Timeout | Image too large or gateway busy | Retry once; if still failing, tell user |

## Rules

- **Local file path** → use `--file` mode.
- **Image URL** → use `--url` mode. URL must be publicly accessible.
- Do NOT `read_file` or `ls` the scripts — just `exec()` them.
- Do NOT write custom `curl` or `python` to call the API — always use `multimodal-call.py`.
- Each image costs ~200–800 prompt tokens. Multimodal and LLM chat share the same token quota.
