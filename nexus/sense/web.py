"""Chrome DevTools Protocol (CDP) integration for web perception.

Connects to Chrome's remote debugging port to get rich web page info:
DOM structure, page content, JavaScript execution, network state.

Requires Chrome running with: --remote-debugging-port=9222
Or launched via: open -a "Google Chrome" --args --remote-debugging-port=9222

This is a PERCEPTION ENHANCEMENT — it enriches see() output when Chrome
is the active app. Falls back gracefully to accessibility tree if CDP
is unavailable.
"""

import json
import urllib.request
import threading

CDP_PORT = 9222
CDP_URL = f"http://localhost:{CDP_PORT}"

# Cache connection to avoid reconnecting every call
_ws = None
_ws_lock = threading.Lock()
_msg_id = 0


def cdp_available():
    """Check if Chrome's debugging port is accessible."""
    try:
        urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=0.5)
        return True
    except Exception:
        return False


def _get_targets():
    """Get list of debuggable targets (tabs)."""
    try:
        resp = urllib.request.urlopen(f"{CDP_URL}/json", timeout=1)
        return json.loads(resp.read())
    except Exception:
        return []


def _get_active_target():
    """Get the active/visible tab's WebSocket URL."""
    targets = _get_targets()
    # Prefer 'page' type targets
    pages = [t for t in targets if t.get("type") == "page"]
    if not pages:
        return None
    # The first page is usually the active tab
    return pages[0]


def _connect(ws_url):
    """Connect to a CDP target via WebSocket."""
    global _ws
    import websocket
    with _ws_lock:
        if _ws:
            try:
                _ws.close()
            except Exception:
                pass
        _ws = websocket.create_connection(ws_url, timeout=5)
    return _ws


def _send(method, params=None, timeout=5):
    """Send a CDP command and wait for the response."""
    global _msg_id, _ws
    if not _ws:
        return None

    with _ws_lock:
        _msg_id += 1
        msg_id = _msg_id

    msg = {"id": msg_id, "method": method}
    if params:
        msg["params"] = params

    try:
        _ws.send(json.dumps(msg))
        # Read responses until we get ours (skip events)
        deadline = __import__("time").time() + timeout
        while __import__("time").time() < deadline:
            _ws.settimeout(timeout)
            raw = _ws.recv()
            data = json.loads(raw)
            if data.get("id") == msg_id:
                if "error" in data:
                    return {"error": data["error"].get("message", str(data["error"]))}
                return data.get("result", {})
    except Exception as e:
        return {"error": str(e)}

    return {"error": "timeout"}


def connect():
    """Connect to the active Chrome tab. Returns True on success."""
    target = _get_active_target()
    if not target:
        return False
    ws_url = target.get("webSocketDebuggerUrl")
    if not ws_url:
        return False
    try:
        _connect(ws_url)
        return True
    except Exception:
        return False


def disconnect():
    """Close the CDP connection."""
    global _ws
    with _ws_lock:
        if _ws:
            try:
                _ws.close()
            except Exception:
                pass
            _ws = None


def page_info():
    """Get current page URL, title, and basic info."""
    target = _get_active_target()
    if not target:
        return None
    return {
        "url": target.get("url", ""),
        "title": target.get("title", ""),
    }


def page_content(max_length=3000):
    """Get the visible text content of the page.

    Returns a compact text representation of the page content,
    suitable for AI consumption without screenshots.
    """
    if not _ws:
        if not connect():
            return None

    # Get the page text using JavaScript
    result = _send("Runtime.evaluate", {
        "expression": """
        (() => {
            // Get visible text, forms, links — compact representation
            const parts = [];

            // Page title
            parts.push('# ' + document.title);
            parts.push('URL: ' + location.href);
            parts.push('');

            // Forms and inputs
            const inputs = document.querySelectorAll('input, textarea, select');
            if (inputs.length > 0) {
                parts.push('## Inputs');
                inputs.forEach((el, i) => {
                    const label = el.labels?.[0]?.textContent?.trim() ||
                                  el.getAttribute('aria-label') ||
                                  el.getAttribute('placeholder') ||
                                  el.name || el.id || `input_${i}`;
                    const type = el.type || el.tagName.toLowerCase();
                    const value = el.value || '';
                    const checked = el.checked !== undefined ? ` [${el.checked ? 'x' : ' '}]` : '';
                    parts.push(`  ${label} (${type}): "${value}"${checked}`);
                });
                parts.push('');
            }

            // Links
            const links = document.querySelectorAll('a[href]');
            if (links.length > 0) {
                parts.push('## Links (' + links.length + ')');
                const shown = Array.from(links).slice(0, 20);
                shown.forEach(a => {
                    const text = a.textContent.trim().substring(0, 60);
                    if (text) parts.push(`  [${text}](${a.href})`);
                });
                if (links.length > 20) parts.push(`  ... and ${links.length - 20} more`);
                parts.push('');
            }

            // Buttons
            const buttons = document.querySelectorAll('button, [role="button"], input[type="submit"]');
            if (buttons.length > 0) {
                parts.push('## Buttons');
                buttons.forEach(b => {
                    const text = b.textContent?.trim() || b.value || b.getAttribute('aria-label') || '(unnamed)';
                    const disabled = b.disabled ? ' [disabled]' : '';
                    parts.push(`  [${text.substring(0, 40)}]${disabled}`);
                });
                parts.push('');
            }

            // Main text content (body text, stripped of scripts/styles)
            const walker = document.createTreeWalker(
                document.body,
                NodeFilter.SHOW_TEXT,
                {
                    acceptNode: (node) => {
                        const parent = node.parentElement;
                        if (!parent) return NodeFilter.FILTER_REJECT;
                        const tag = parent.tagName;
                        if (['SCRIPT', 'STYLE', 'NOSCRIPT', 'SVG'].includes(tag))
                            return NodeFilter.FILTER_REJECT;
                        if (parent.offsetParent === null && tag !== 'BODY')
                            return NodeFilter.FILTER_REJECT;
                        const text = node.textContent.trim();
                        if (text.length < 2) return NodeFilter.FILTER_REJECT;
                        return NodeFilter.FILTER_ACCEPT;
                    }
                }
            );

            const texts = [];
            let totalLen = 0;
            while (walker.nextNode() && totalLen < 2000) {
                const t = walker.currentNode.textContent.trim();
                if (t && !texts.includes(t)) {
                    texts.push(t);
                    totalLen += t.length;
                }
            }
            if (texts.length > 0) {
                parts.push('## Content');
                parts.push(texts.join('\\n'));
            }

            return parts.join('\\n');
        })()
        """,
        "returnByValue": True,
    })

    if not result or "error" in result:
        return None

    text = result.get("result", {}).get("value", "")
    return text[:max_length] if text else None


def run_js(expression):
    """Execute JavaScript in the page and return the result.

    Returns the result value, or an error dict.
    """
    if not _ws:
        if not connect():
            return {"ok": False, "error": "CDP not connected"}

    result = _send("Runtime.evaluate", {
        "expression": expression,
        "returnByValue": True,
        "awaitPromise": True,
    })

    if not result or "error" in result:
        return {"ok": False, "error": result.get("error", "evaluation failed") if result else "no response"}

    r = result.get("result", {})
    if r.get("subtype") == "error":
        return {"ok": False, "error": r.get("description", "JS error")}

    return {"ok": True, "value": r.get("value"), "type": r.get("type", "undefined")}


def navigate(url):
    """Navigate the active tab to a URL."""
    if not _ws:
        if not connect():
            return {"ok": False, "error": "CDP not connected"}

    result = _send("Page.navigate", {"url": url})
    if result and "error" not in result:
        return {"ok": True, "url": url}
    return {"ok": False, "error": result.get("error", "navigation failed") if result else "no response"}


def click_element_js(selector):
    """Click an element by CSS selector via JavaScript."""
    return run_js(f"""
        (() => {{
            const el = document.querySelector({json.dumps(selector)});
            if (!el) return 'Element not found: ' + {json.dumps(selector)};
            el.click();
            return 'Clicked: ' + (el.textContent || el.tagName).trim().substring(0, 50);
        }})()
    """)


def type_in_element_js(selector, text):
    """Type text into an element by CSS selector."""
    return run_js(f"""
        (() => {{
            const el = document.querySelector({json.dumps(selector)});
            if (!el) return 'Element not found: ' + {json.dumps(selector)};
            el.focus();
            el.value = {json.dumps(text)};
            el.dispatchEvent(new Event('input', {{bubbles: true}}));
            el.dispatchEvent(new Event('change', {{bubbles: true}}));
            return 'Typed in: ' + (el.name || el.id || el.tagName);
        }})()
    """)


def tab_list():
    """List all Chrome tabs with their URLs and titles."""
    targets = _get_targets()
    pages = [t for t in targets if t.get("type") == "page"]
    return [{"title": p.get("title", ""), "url": p.get("url", "")} for p in pages]
