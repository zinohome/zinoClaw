#!/usr/bin/env python3
"""
Multimodal image analysis via NoDesk AI Gateway.

Mode 1 — raw messages JSON (advanced):
  python3 multimodal-call.py '<messages_json>' [max_tokens] [model]

Mode 2 — local file shortcut:
  python3 multimodal-call.py --file <image_path> '<prompt>' [max_tokens] [model]

Mode 3 — image URL shortcut:
  python3 multimodal-call.py --url '<image_url>' '<prompt>' [max_tokens] [model]
"""

import json
import sys
import os
import base64
import tempfile
import subprocess
import shutil
from urllib.request import urlopen, Request
from urllib.error import URLError

GATEWAY_BASE = "https://llm-gateway-api.nodesk.tech"
DESKCLAW_HOME = os.path.join(os.path.expanduser("~"), ".deskclaw")
CONFIG_PATH = os.path.join(DESKCLAW_HOME, "nanobot", "config.json")
SETTINGS_PATH = os.path.join(DESKCLAW_HOME, "deskclaw-settings.json")
MAX_RAW_SIZE = 500_000
RESIZE_MAX_DIM = 1536
JPEG_QUALITY = 80


def _extract_ep_token(url_str):
    if url_str and "/ep/" in url_str:
        return url_str.split("/ep/")[1].split("/")[0]
    return ""


def load_auth():
    # 1) config.json — providers.custom (default when user hasn't overridden)
    try:
        with open(CONFIG_PATH) as f:
            config = json.load(f)
        custom = config.get("providers", {}).get("custom", {})
        api_base = custom.get("api_base", "") or custom.get("baseUrl", "")
        ep = _extract_ep_token(api_base)
        if ep:
            return None, ep
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # 2) deskclaw-settings.json — settings.gatewayConfig (always preserved by client)
    try:
        with open(SETTINGS_PATH) as f:
            settings = json.load(f)
        gw = settings.get("settings.gatewayConfig", {})
        if isinstance(gw, dict):
            ep = _extract_ep_token(gw.get("apiUrl", ""))
            if ep:
                return None, ep
            gw_key = gw.get("apiKey", "")
            if gw_key:
                return gw_key, None
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    return None, None


def get_endpoint_and_headers(api_key, ep_token):
    headers = {"Content-Type": "application/json"}
    if api_key:
        url = f"{GATEWAY_BASE}/deskclaw/v1/multimodal/"
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        url = f"{GATEWAY_BASE}/deskclaw/v1/ep/{ep_token}/multimodal/"
    return url, headers


def send_request(url, headers, body):
    data = json.dumps(body).encode("utf-8")
    req = Request(url, data=data, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except URLError as e:
        if hasattr(e, "read"):
            try:
                return json.loads(e.read().decode("utf-8"))
            except Exception:
                pass
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


def detect_mime(filepath):
    """Detect image MIME subtype from file content bytes."""
    try:
        with open(filepath, "rb") as f:
            header = f.read(32)
    except OSError:
        return "jpeg"

    if header[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if header[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if header[:4] == b"GIF8":
        return "gif"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    return "jpeg"


def mime_from_ext(path):
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    return {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}.get(ext, "jpeg")


def compress_image(src_path, dst_path):
    """Try to compress/resize a large image. Returns True on success."""
    if shutil.which("sips"):
        r = subprocess.run(
            ["sips", "--resampleHeightWidthMax", str(RESIZE_MAX_DIM),
             "--setProperty", "format", "jpeg",
             "--setProperty", "formatOptions", str(JPEG_QUALITY),
             src_path, "--out", dst_path],
            capture_output=True,
        )
        if r.returncode == 0 and os.path.isfile(dst_path):
            return True

    if shutil.which("magick"):
        r = subprocess.run(
            ["magick", src_path, "-resize", f"{RESIZE_MAX_DIM}x{RESIZE_MAX_DIM}>",
             "-quality", str(JPEG_QUALITY), dst_path],
            capture_output=True,
        )
        if r.returncode == 0 and os.path.isfile(dst_path):
            return True

    try:
        from PIL import Image
        with Image.open(src_path) as img:
            img.thumbnail((RESIZE_MAX_DIM, RESIZE_MAX_DIM), Image.LANCZOS)
            img.save(dst_path, "JPEG", quality=JPEG_QUALITY)
            return True
    except Exception:
        pass

    return False


def encode_file_to_base64(filepath):
    with open(filepath, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def download_url(url, dst_path):
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=30) as resp:
            with open(dst_path, "wb") as f:
                shutil.copyfileobj(resp, f)
        return os.path.getsize(dst_path) > 0
    except Exception:
        return False


def build_base64_body(image_path, prompt, model, max_tokens):
    tmpdir = tempfile.mkdtemp()
    try:
        file_size = os.path.getsize(image_path)
        work_file = image_path
        mime = detect_mime(image_path)

        if file_size > MAX_RAW_SIZE:
            resized = os.path.join(tmpdir, "resized.jpg")
            if compress_image(image_path, resized):
                work_file = resized
                mime = "jpeg"

        b64 = encode_file_to_base64(work_file)
        data_uri = f"data:image/{mime};base64,{b64}"
        return {
            "model": model,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ]}],
            "max_tokens": max_tokens,
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def err_exit(msg):
    print(json.dumps({"error": msg}, ensure_ascii=False))
    sys.exit(1)


def main():
    args = sys.argv[1:]
    if not args:
        err_exit("Usage: multimodal-call.py --file <path> <prompt> | --url <url> <prompt> | <messages_json>")

    api_key, ep_token = load_auth()
    if not api_key and not ep_token:
        err_exit("Auth not found in ~/.deskclaw/nanobot/config.json. "
                 "Need providers.custom.apiKey or providers.custom.api_base with /ep/ token.")

    url, headers = get_endpoint_and_headers(api_key, ep_token)

    # --- Mode 2: --file ---
    if args[0] == "--file":
        image_path = args[1] if len(args) > 1 else ""
        prompt = args[2] if len(args) > 2 else "Describe this image in detail."
        max_tokens = int(args[3]) if len(args) > 3 else 1500
        model = args[4] if len(args) > 4 else "kimi-k2.5"

        if not image_path or not os.path.isfile(image_path):
            err_exit(f"File not found: {image_path}")

        body = build_base64_body(image_path, prompt, model, max_tokens)
        result = send_request(url, headers, body)
        print(json.dumps(result, ensure_ascii=False))
        return

    # --- Mode 3: --url ---
    if args[0] == "--url":
        image_url = args[1] if len(args) > 1 else ""
        prompt = args[2] if len(args) > 2 else "Describe this image in detail."
        max_tokens = int(args[3]) if len(args) > 3 else 1500

        if not image_url:
            err_exit("Usage: multimodal-call.py --url <image_url> <prompt>")

        body = {
            "model": "glm-5v-turbo",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}},
            ]}],
            "max_tokens": max_tokens,
        }
        result = send_request(url, headers, body)

        if isinstance(result.get("error"), dict) and result["error"].get("code") == "1210":
            tmpdir = tempfile.mkdtemp()
            try:
                dl_path = os.path.join(tmpdir, "downloaded_img")
                if download_url(image_url, dl_path):
                    body = build_base64_body(dl_path, prompt, "kimi-k2.5", max_tokens)
                    result = send_request(url, headers, body)
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)

        print(json.dumps(result, ensure_ascii=False))
        return

    # --- Mode 1: raw messages JSON ---
    messages_raw = args[0]
    max_tokens = int(args[1]) if len(args) > 1 else 1500
    model = args[2] if len(args) > 2 else "kimi-k2.5"

    try:
        messages = json.loads(messages_raw)
    except json.JSONDecodeError as e:
        err_exit(f"Failed to parse messages JSON: {e}")

    body = {"model": model, "messages": messages, "max_tokens": max_tokens}
    result = send_request(url, headers, body)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
