"""Electron app automation — detect and connect to Electron apps via CDP.

Electron apps (VS Code, Discord, Slack, Figma) are Chromium under the hood.
When launched with --remote-debugging-port=NNNN, Nexus web-* commands work on them.

Pure functions: params → dict. No side effects beyond network requests.
"""

import json
import socket
import urllib.request
import urllib.error


# Common Electron app CDP ports (convention)
KNOWN_APPS = {
    9222: "Chrome / Chromium",
    9223: "VS Code",
    9224: "Discord",
    9225: "Figma",
    9226: "Slack",
    9227: "Obsidian",
    9228: "Spotify",
}

# Range to scan for auto-detection
SCAN_RANGE = range(9222, 9235)


def _port_open(port: int, timeout: float = 0.3) -> bool:
    """Quick check if a TCP port is open."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        result = s.connect_ex(("127.0.0.1", port))
        s.close()
        return result == 0
    except OSError:
        return False


def _probe_cdp(port: int, timeout: float = 1.0) -> dict | None:
    """Probe a CDP port. Returns version info dict or None if not reachable."""
    url = "http://localhost:%d/json/version" % port
    try:
        req = urllib.request.urlopen(url, timeout=timeout)
        data = json.loads(req.read().decode())
        req.close()
        return data
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return None


def detect() -> dict:
    """Scan common CDP ports to find running Chromium/Electron apps.

    Returns:
        {"command": "electron-detect", "apps": [{port, browser, user_agent, ...}], "count": N}
    """
    apps = []
    for port in SCAN_RANGE:
        # Fast socket check first — skip closed ports without HTTP overhead
        if not _port_open(port):
            continue
        info = _probe_cdp(port)
        if info is None:
            continue

        browser = info.get("Browser", "Unknown")
        user_agent = info.get("User-Agent", "")
        ws_url = info.get("webSocketDebuggerUrl", "")

        # Try to identify the app
        app_name = KNOWN_APPS.get(port, "")
        if not app_name:
            # Guess from browser string
            b_lower = browser.lower()
            if "electron" in b_lower or "code" in b_lower:
                app_name = "Electron App"
            elif "chrome" in b_lower:
                app_name = "Chrome"
            else:
                app_name = browser

        apps.append({
            "port": port,
            "app": app_name,
            "browser": browser,
            "user_agent": user_agent,
            "ws_url": ws_url,
        })

    return {
        "command": "electron-detect",
        "apps": apps,
        "count": len(apps),
    }


def connect(port: int) -> dict:
    """Verify connection to an Electron app's CDP port.

    Returns app info if connectable. All subsequent web-* commands should
    use --port to target this app.

    Returns:
        {"command": "electron-connect", "ok": True, "port": N, "browser": ..., ...}
    """
    info = _probe_cdp(port, timeout=3.0)
    if info is None:
        return {
            "command": "electron-connect",
            "ok": False,
            "error": "Cannot connect to CDP on port %d. Is the app running with --remote-debugging-port=%d?" % (port, port),
        }

    return {
        "command": "electron-connect",
        "ok": True,
        "port": port,
        "browser": info.get("Browser", "Unknown"),
        "user_agent": info.get("User-Agent", ""),
        "ws_url": info.get("webSocketDebuggerUrl", ""),
        "cdp_url": "http://localhost:%d" % port,
    }


def list_targets(port: int) -> dict:
    """List all CDP targets (pages/tabs) on a port.

    Returns:
        {"command": "electron-targets", "port": N, "targets": [...], "count": N}
    """
    url = "http://localhost:%d/json" % port
    try:
        req = urllib.request.urlopen(url, timeout=3.0)
        targets = json.loads(req.read().decode())
        req.close()
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        return {
            "command": "electron-targets",
            "ok": False,
            "error": "Cannot list targets on port %d: %s" % (port, str(e)),
        }

    # Filter to page targets only (skip service workers, background pages, etc.)
    pages = []
    for t in targets:
        if t.get("type") == "page":
            pages.append({
                "title": t.get("title", ""),
                "url": t.get("url", ""),
                "id": t.get("id", ""),
            })

    return {
        "command": "electron-targets",
        "port": port,
        "targets": pages,
        "count": len(pages),
    }
