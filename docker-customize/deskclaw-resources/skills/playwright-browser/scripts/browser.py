#!/usr/bin/env python3
"""
Playwright 浏览器自动化工具
支持：导航、点击、输入、截图、提取内容、滚动、等待、多标签页、Cookie 管理等
"""

import sys
import json
import os
import random
import time
import subprocess

def find_chrome():
    """检测系统已安装的 Chromium 系浏览器，返回路径"""
    import platform
    candidates = []
    if platform.system() == "Darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ]
    elif platform.system() == "Linux":
        import shutil
        for name in ["google-chrome", "chromium-browser", "chromium", "microsoft-edge", "brave-browser"]:
            path = shutil.which(name)
            if path:
                return path

    for p in candidates:
        if os.path.exists(p):
            return p
    return None


STEALTH_JS = """
() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

    window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {} };

    Object.defineProperty(navigator, 'plugins', {
        get: () => [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
            { name: 'Native Client', filename: 'internal-nacl-plugin' },
        ],
    });

    Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });

    const origQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (params) =>
        params.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : origQuery(params);

    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
    Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(param) {
        if (param === 37445) return 'Intel Inc.';
        if (param === 37446) return 'Intel Iris OpenGL Engine';
        return getParameter.call(this, param);
    };
}
"""


def _human_delay(base=0.5, jitter=0.8):
    """随机延迟，模拟人类操作节奏"""
    time.sleep(base + random.uniform(0, jitter))


def _human_scroll(page, steps=None):
    """分段平滑滚动，模拟真人浏览"""
    total_height = page.evaluate("document.body.scrollHeight")
    viewport_height = page.evaluate("window.innerHeight")
    current = page.evaluate("window.scrollY")

    if steps is None:
        steps = random.randint(3, 6)

    remaining = total_height - current - viewport_height
    if remaining <= 0:
        return

    for _ in range(steps):
        chunk = remaining / steps + random.randint(-80, 80)
        chunk = max(100, chunk)
        current += chunk
        page.evaluate(f"window.scrollTo({{top: {int(current)}, behavior: 'smooth'}})")
        _human_delay(0.4, 0.6)


def get_browser_context(headless=True, session_file=None):
    """获取浏览器上下文，直接使用系统已安装的 Chrome，无需额外下载"""
    from playwright.sync_api import sync_playwright

    chrome_path = find_chrome()
    if not chrome_path:
        raise RuntimeError(
            "未检测到 Chromium 系浏览器。请安装 Google Chrome 或 Microsoft Edge。\n"
            "Chrome 下载：https://www.google.cn/chrome/\n"
            "Edge 下载：https://www.microsoft.com/zh-cn/edge"
        )

    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=headless,
        executable_path=chrome_path,
        args=[
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-blink-features=AutomationControlled",
        ]
    )

    ctx_opts = {
        "viewport": {"width": 1280, "height": 720},
        "user_agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "extra_http_headers": {
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
        },
    }
    if session_file and os.path.exists(session_file):
        ctx_opts["storage_state"] = session_file
    context = browser.new_context(**ctx_opts)

    context.add_init_script(STEALTH_JS)

    page = context.new_page()
    return pw, browser, context, page


# ==================== 命令实现 ====================

def cmd_navigate(args):
    """打开网页"""
    url = args["url"]
    wait = args.get("wait_for", None)
    timeout = args.get("timeout", 30000)
    session = args.get("session_file", None)
    headless = args.get("headless", True)

    pw, browser, context, page = get_browser_context(headless=headless, session_file=session)
    try:
        page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        if wait:
            page.wait_for_selector(wait, timeout=timeout)
        title = page.title()
        current_url = page.url
        return {"status": "ok", "title": title, "url": current_url}
    finally:
        browser.close()
        pw.stop()


def cmd_screenshot(args):
    """网页截图"""
    url = args["url"]
    output = args.get("output", "/tmp/screenshot.png")
    full_page = args.get("full_page", False)
    wait = args.get("wait_for", None)
    timeout = args.get("timeout", 30000)
    session = args.get("session_file", None)

    pw, browser, context, page = get_browser_context(session_file=session)
    try:
        page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        if wait:
            page.wait_for_selector(wait, timeout=timeout)
        time.sleep(1)
        page.screenshot(path=output, full_page=full_page)
        return {"status": "ok", "file": output, "title": page.title()}
    finally:
        browser.close()
        pw.stop()


def cmd_click(args):
    """点击元素"""
    url = args.get("url")
    selector = args["selector"]
    wait = args.get("wait_for", None)
    timeout = args.get("timeout", 30000)
    session = args.get("session_file", None)
    screenshot_after = args.get("screenshot_after", None)

    pw, browser, context, page = get_browser_context(session_file=session)
    try:
        if url:
            page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        if wait:
            page.wait_for_selector(wait, timeout=timeout)
        with context.expect_page(timeout=3000) as new_page_info:
            try:
                page.click(selector, timeout=timeout)
            except Exception:
                pass
        try:
            new_page = new_page_info.value
            new_page.wait_for_load_state("domcontentloaded", timeout=10000)
            page = new_page
        except Exception:
            pass
        time.sleep(0.5)
        result = {"status": "ok", "clicked": selector, "url": page.url, "title": page.title()}
        if screenshot_after:
            page.screenshot(path=screenshot_after)
            result["screenshot"] = screenshot_after
        return result
    finally:
        browser.close()
        pw.stop()


def cmd_input(args):
    """在输入框中输入文字"""
    url = args.get("url")
    selector = args["selector"]
    text = args["text"]
    clear = args.get("clear", True)
    press_enter = args.get("press_enter", False)
    timeout = args.get("timeout", 30000)
    session = args.get("session_file", None)
    screenshot_after = args.get("screenshot_after", None)

    pw, browser, context, page = get_browser_context(session_file=session)
    try:
        if url:
            page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        try:
            if clear:
                page.fill(selector, text, timeout=timeout)
            else:
                page.type(selector, text, timeout=timeout)
        except Exception:
            page.evaluate(f"""() => {{
                const el = document.querySelector('{selector}');
                if (el) {{ el.focus(); el.value = ''; }}
            }}""")
            page.keyboard.type(text, delay=50)
        if press_enter:
            page.press(selector, "Enter")
            time.sleep(1)
        result = {"status": "ok", "selector": selector, "text": text, "url": page.url}
        if screenshot_after:
            page.screenshot(path=screenshot_after)
            result["screenshot"] = screenshot_after
        return result
    finally:
        browser.close()
        pw.stop()


def cmd_extract(args):
    """提取页面内容"""
    url = args["url"]
    mode = args.get("mode", "text")
    selector = args.get("selector", "body")
    wait = args.get("wait_for", None)
    timeout = args.get("timeout", 30000)
    session = args.get("session_file", None)

    pw, browser, context, page = get_browser_context(session_file=session)
    try:
        page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        if wait:
            page.wait_for_selector(wait, timeout=timeout)
        time.sleep(1)

        if mode == "text":
            content = page.inner_text(selector)
        elif mode == "html":
            content = page.inner_html(selector)
        elif mode == "all_links":
            links = page.eval_on_selector_all("a[href]", "els => els.map(e => ({text: e.innerText.trim(), href: e.href})).filter(l => l.text)")
            return {"status": "ok", "links": links, "count": len(links)}
        elif mode == "table":
            rows = page.eval_on_selector_all(
                f"{selector} tr",
                "rows => rows.map(r => Array.from(r.querySelectorAll('td,th')).map(c => c.innerText.trim()))"
            )
            return {"status": "ok", "rows": rows, "count": len(rows)}
        else:
            content = page.inner_text(selector)

        if len(content) > 50000:
            content = content[:50000] + "\n...(内容过长，已截断)"

        return {"status": "ok", "content": content, "length": len(content), "title": page.title()}
    finally:
        browser.close()
        pw.stop()


def cmd_scroll(args):
    """滚动页面并提取内容"""
    url = args["url"]
    selector = args.get("selector", None)
    times = args.get("times", 3)
    delay = args.get("delay", 1000)
    timeout = args.get("timeout", 30000)
    session = args.get("session_file", None)
    screenshot_after = args.get("screenshot_after", None)

    pw, browser, context, page = get_browser_context(session_file=session)
    try:
        page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        time.sleep(1)

        items_before = 0
        if selector:
            items_before = page.eval_on_selector_all(selector, "els => els.length")

        for i in range(times):
            _human_scroll(page)
            _human_delay(delay / 1000 * 0.5, delay / 1000 * 0.5)

        items_after = 0
        collected = []
        if selector:
            items_after = page.eval_on_selector_all(selector, "els => els.length")
            collected = page.eval_on_selector_all(selector, "els => els.map(e => e.innerText.trim())")

        result = {
            "status": "ok",
            "scrolled": times,
            "items_before": items_before,
            "items_after": items_after,
            "collected": collected
        }
        if screenshot_after:
            page.screenshot(path=screenshot_after, full_page=True)
            result["screenshot"] = screenshot_after
        return result
    finally:
        browser.close()
        pw.stop()


def cmd_select(args):
    """下拉框选择"""
    url = args.get("url")
    selector = args["selector"]
    value = args.get("value")
    label = args.get("label")
    timeout = args.get("timeout", 30000)
    session = args.get("session_file", None)

    pw, browser, context, page = get_browser_context(session_file=session)
    try:
        if url:
            page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        if value:
            page.select_option(selector, value=value, timeout=timeout)
        elif label:
            page.select_option(selector, label=label, timeout=timeout)
        return {"status": "ok", "selector": selector, "selected": value or label}
    finally:
        browser.close()
        pw.stop()


def cmd_wait(args):
    """等待元素出现"""
    url = args.get("url")
    selector = args["selector"]
    state = args.get("state", "visible")
    timeout = args.get("timeout", 30000)
    session = args.get("session_file", None)

    pw, browser, context, page = get_browser_context(session_file=session)
    try:
        if url:
            page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        page.wait_for_selector(selector, state=state, timeout=timeout)
        return {"status": "ok", "selector": selector, "state": state}
    finally:
        browser.close()
        pw.stop()


def cmd_evaluate(args):
    """执行 JavaScript"""
    url = args.get("url")
    script = args["script"]
    timeout = args.get("timeout", 30000)
    session = args.get("session_file", None)

    pw, browser, context, page = get_browser_context(session_file=session)
    try:
        if url:
            page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        result = page.evaluate(script)
        return {"status": "ok", "result": result}
    finally:
        browser.close()
        pw.stop()


def cmd_save_session(args):
    """保存登录状态"""
    url = args["url"]
    output = args.get("output", "/tmp/browser_session.json")
    wait_seconds = args.get("wait_seconds", 120)
    login_check = args.get("login_check", None)

    pw, browser, context, page = get_browser_context(headless=False)
    try:
        page.goto(url, wait_until="domcontentloaded")
        print(f"浏览器已打开 {url}", file=sys.stderr)
        print(f"请在 {wait_seconds} 秒内完成登录操作...", file=sys.stderr)

        if login_check:
            poll_interval = 2
            elapsed = 0
            while elapsed < wait_seconds:
                time.sleep(poll_interval)
                elapsed += poll_interval
                try:
                    current_url = page.url
                    cookies = context.cookies()
                    cookie_names = {c["name"] for c in cookies}

                    if login_check.get("url_contains"):
                        if login_check["url_contains"] not in current_url:
                            continue
                    if login_check.get("url_not_contains"):
                        if login_check["url_not_contains"] in current_url:
                            continue
                    if login_check.get("cookie_exists"):
                        if login_check["cookie_exists"] not in cookie_names:
                            continue

                    print(f"检测到登录成功 (耗时 {elapsed}s)，等待 3 秒让 cookie 稳定...", file=sys.stderr)
                    time.sleep(3)
                    break
                except Exception:
                    continue
            else:
                print(f"等待超时 ({wait_seconds}s)，仍将保存当前状态", file=sys.stderr)
        else:
            time.sleep(wait_seconds)

        context.storage_state(path=output)
        cookies = context.cookies()
        return {
            "status": "ok",
            "session_file": output,
            "cookie_count": len(cookies),
            "domains": list({c["domain"] for c in cookies}),
            "message": f"登录状态已保存到 {output}（{len(cookies)} 个 cookie）",
        }
    finally:
        browser.close()
        pw.stop()


def cmd_multi_step(args):
    """多步骤自动化流程"""
    steps = args["steps"]
    session = args.get("session_file", None)
    headless = args.get("headless", True)

    pw, browser, context, page = get_browser_context(headless=headless, session_file=session)
    results = []
    try:
        for i, step in enumerate(steps):
            action = step["action"]
            try:
                if action == "goto":
                    page.goto(step["url"], timeout=step.get("timeout", 30000), wait_until="domcontentloaded")
                    results.append({"step": i+1, "action": action, "status": "ok", "url": page.url})

                elif action == "click":
                    old_url = page.url
                    new_page = None
                    try:
                        with context.expect_page(timeout=3000) as new_page_info:
                            page.click(step["selector"], timeout=step.get("timeout", 10000))
                        new_page = new_page_info.value
                        new_page.wait_for_load_state("domcontentloaded", timeout=10000)
                        page = new_page
                    except Exception:
                        if not new_page:
                            try:
                                page.click(step["selector"], timeout=step.get("timeout", 10000))
                            except Exception:
                                pass
                            time.sleep(step.get("delay", 0.5))
                            try:
                                page.wait_for_load_state("domcontentloaded", timeout=5000)
                            except Exception:
                                pass
                    time.sleep(step.get("delay", 0.5))
                    results.append({"step": i+1, "action": action, "status": "ok", "selector": step["selector"], "url": page.url, "navigated": page.url != old_url})

                elif action == "input":
                    sel = step["selector"]
                    txt = step["text"]
                    try:
                        if step.get("clear", True):
                            page.fill(sel, txt, timeout=step.get("timeout", 10000))
                        else:
                            page.type(sel, txt, timeout=step.get("timeout", 10000))
                    except Exception:
                        page.evaluate(f"""() => {{
                            const el = document.querySelector('{sel}');
                            if (el) {{ el.focus(); el.value = ''; }}
                        }}""")
                        page.keyboard.type(txt, delay=50)
                    results.append({"step": i+1, "action": action, "status": "ok", "selector": sel})

                elif action == "press":
                    page.press(step.get("selector", "body"), step["key"])
                    time.sleep(step.get("delay", 0.5))
                    results.append({"step": i+1, "action": action, "status": "ok", "key": step["key"]})

                elif action == "wait":
                    page.wait_for_selector(step["selector"], state=step.get("state", "visible"), timeout=step.get("timeout", 10000))
                    results.append({"step": i+1, "action": action, "status": "ok", "selector": step["selector"]})

                elif action == "screenshot":
                    path = step.get("output", f"/tmp/step_{i+1}.png")
                    page.screenshot(path=path, full_page=step.get("full_page", False))
                    results.append({"step": i+1, "action": action, "status": "ok", "file": path})

                elif action == "extract":
                    sel = step.get("selector", "body")
                    text = page.inner_text(sel)
                    if len(text) > 10000:
                        text = text[:10000] + "...(截断)"
                    results.append({"step": i+1, "action": action, "status": "ok", "content": text})

                elif action == "select":
                    if "value" in step:
                        page.select_option(step["selector"], value=step["value"])
                    elif "label" in step:
                        page.select_option(step["selector"], label=step["label"])
                    results.append({"step": i+1, "action": action, "status": "ok"})

                elif action == "scroll":
                    _human_scroll(page)
                    _human_delay(0.3, float(step.get("delay", 1)))
                    results.append({"step": i+1, "action": action, "status": "ok"})

                elif action == "sleep":
                    base = step.get("seconds", 1)
                    _human_delay(base * 0.7, base * 0.6)
                    results.append({"step": i+1, "action": action, "status": "ok"})

                elif action == "evaluate":
                    r = page.evaluate(step["script"])
                    results.append({"step": i+1, "action": action, "status": "ok", "result": r})

                elif action == "click_and_goto":
                    sel = step["selector"]
                    old_url = page.url
                    navigated = False

                    # 尝试 1：正常 click，看是否新标签页或当前页跳转
                    new_page = None
                    try:
                        with context.expect_page(timeout=3000) as new_page_info:
                            page.click(sel, timeout=step.get("timeout", 10000))
                        new_page = new_page_info.value
                        new_page.wait_for_load_state("domcontentloaded", timeout=10000)
                        page = new_page
                        navigated = True
                    except Exception:
                        if not new_page:
                            try:
                                page.click(sel, timeout=step.get("timeout", 10000))
                            except Exception:
                                pass
                            time.sleep(1)
                            try:
                                page.wait_for_load_state("domcontentloaded", timeout=3000)
                            except Exception:
                                pass
                            if page.url != old_url:
                                navigated = True

                    # 尝试 2：如果没跳转，用 JS 获取 href 然后 goto
                    if not navigated:
                        try:
                            href = page.evaluate(f"document.querySelector('{sel}')?.href || ''")
                            if href:
                                page.goto(href, timeout=step.get("timeout", 30000), wait_until="domcontentloaded")
                                navigated = True
                        except Exception:
                            pass

                    time.sleep(step.get("delay", 0.5))
                    results.append({
                        "step": i+1, "action": action, "status": "ok",
                        "selector": sel, "url": page.url,
                        "title": page.title(), "navigated": navigated
                    })

                else:
                    results.append({"step": i+1, "action": action, "status": "error", "error": f"未知操作: {action}"})

            except Exception as e:
                results.append({"step": i+1, "action": action, "status": "error", "error": str(e)})
                if step.get("stop_on_error", True):
                    break

        if session and os.path.exists(session):
            try:
                context.storage_state(path=session)
            except Exception:
                pass

        return {"status": "ok", "total_steps": len(steps), "results": results}
    finally:
        browser.close()
        pw.stop()


def cmd_check(args):
    """检查 Playwright 和浏览器是否可用"""
    issues = []

    try:
        import importlib.metadata
        pw_version = importlib.metadata.version("playwright")
    except Exception:
        try:
            import playwright
            pw_version = "installed"
        except ImportError:
            issues.append("playwright 未安装，请执行: pip3 install playwright")
            pw_version = None

    chrome_path = find_chrome()
    if not chrome_path:
        issues.append("未检测到 Chrome/Edge/Chromium 浏览器，请安装 Google Chrome (https://www.google.cn/chrome/)")

    browser_ok = False
    if pw_version and chrome_path:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                b = p.chromium.launch(headless=True, executable_path=chrome_path, args=["--no-first-run", "--no-default-browser-check"])
                b.close()
            browser_ok = True
        except Exception as e:
            issues.append(f"浏览器启动失败: {e}")

    return {
        "status": "ok" if not issues else "issues",
        "playwright_version": pw_version,
        "chrome_path": chrome_path,
        "browser_available": browser_ok,
        "issues": issues
    }


def cmd_install(args):
    """安装 Playwright（浏览器使用系统已安装的 Chrome，无需额外下载）"""
    try:
        import playwright
    except ImportError:
        print("正在安装 playwright...", file=sys.stderr)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright", "-q"])
    return cmd_check({})


# ==================== 入口 ====================

COMMANDS = {
    "navigate": cmd_navigate,
    "screenshot": cmd_screenshot,
    "click": cmd_click,
    "input": cmd_input,
    "extract": cmd_extract,
    "scroll": cmd_scroll,
    "select": cmd_select,
    "wait": cmd_wait,
    "evaluate": cmd_evaluate,
    "save_session": cmd_save_session,
    "multi_step": cmd_multi_step,
    "check": cmd_check,
    "install": cmd_install,
}

def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "用法: python3 browser.py <命令> '<JSON参数>'",
            "commands": {k: v.__doc__.strip() for k, v in COMMANDS.items()}
        }, ensure_ascii=False, indent=2))
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(json.dumps({"error": f"未知命令: {cmd}", "available": list(COMMANDS.keys())}, ensure_ascii=False))
        sys.exit(1)

    args = {}
    if len(sys.argv) > 2:
        raw = sys.argv[2]
        if raw.startswith("@"):
            with open(raw[1:], "r", encoding="utf-8") as f:
                args = json.load(f)
        elif raw == "-":
            args = json.load(sys.stdin)
        else:
            args = json.loads(raw)

    try:
        result = COMMANDS[cmd](args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
