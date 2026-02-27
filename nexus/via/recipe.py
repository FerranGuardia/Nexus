"""Recipe system — direct automation via AppleScript, CLI, and URL schemes.

Recipes intercept natural-language intents BEFORE the GUI verb dispatcher,
executing them 10-50x faster through direct OS APIs. If a recipe fails,
the router silently falls through to GUI automation.

Usage:
    from nexus.via.recipe import recipe, applescript, cli

    @recipe(r"set volume (?:to )?(\\d+)", app=None, priority=50)
    def set_volume(match, pid=None):
        return applescript(f'set volume output volume {match.group(1)}')
"""

import re
import subprocess
from dataclasses import dataclass
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@dataclass
class Recipe:
    name: str                  # "system.set_volume"
    pattern: re.Pattern        # compiled regex
    handler: Callable          # fn(match, pid=None) → dict
    app: Optional[str]         # "mail", "finder", None = any app
    priority: int              # lower = tried first


_registry: list[Recipe] = []
_loaded: bool = False


def recipe(pattern, app=None, priority=50):
    """Decorator to register an intent recipe."""
    compiled = re.compile(pattern, re.IGNORECASE)

    def decorator(fn):
        module = fn.__module__.rsplit(".", 1)[-1] if fn.__module__ else "unknown"
        name = f"{module}.{fn.__name__}"
        r = Recipe(
            name=name,
            pattern=compiled,
            handler=fn,
            app=app.lower() if app else None,
            priority=priority,
        )
        # Replace if already registered (handles module reload)
        for i, existing in enumerate(_registry):
            if existing.name == name:
                _registry[i] = r
                _registry.sort(key=lambda x: x.priority)
                return fn
        _registry.append(r)
        _registry.sort(key=lambda x: x.priority)
        return fn

    return decorator


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def match_recipe(action, pid=None):
    """Find first matching recipe for this action.

    Returns (Recipe, re.Match) or (None, None).
    """
    _ensure_loaded()
    app_name = _current_app(pid)

    for r in _registry:
        # Skip if recipe is app-specific and wrong app
        if r.app and app_name and r.app not in app_name.lower():
            continue
        # If recipe is app-specific and we can't determine current app, skip
        if r.app and not app_name:
            continue

        m = r.pattern.search(action)
        if m:
            return r, m

    return None, None


def execute_recipe(rcp, match, pid=None):
    """Execute a matched recipe. Returns result dict."""
    try:
        result = rcp.handler(match, pid=pid)
        if isinstance(result, dict):
            return result
        return {"ok": True, "result": str(result)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_recipes():
    """List all registered recipes."""
    _ensure_loaded()
    return [
        {
            "name": r.name,
            "pattern": r.pattern.pattern,
            "app": r.app,
            "priority": r.priority,
        }
        for r in _registry
    ]


# ---------------------------------------------------------------------------
# Execution helpers
# ---------------------------------------------------------------------------

def applescript(script):
    """Run AppleScript via native.run_applescript(). Returns result dict."""
    from nexus.act.native import run_applescript
    result = run_applescript(script)
    # Normalize: native returns {"ok", "stdout", "stderr"}
    if result.get("ok"):
        return {"ok": True, "result": result.get("stdout", "")}
    return {"ok": False, "error": result.get("stderr") or result.get("error", "AppleScript failed")}


def cli(command, timeout=30):
    """Run a shell command. Returns result dict."""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode == 0:
            return {"ok": True, "result": result.stdout.strip()}
        return {"ok": False, "error": result.stderr.strip() or f"exit code {result.returncode}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Timed out after {timeout}s"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def url_scheme(url):
    """Open a URL scheme (x-apple.systempreferences:, etc.)."""
    return cli(f'open "{url}"')


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _current_app(pid):
    """Get app name for PID, or frontmost app name."""
    if pid:
        try:
            from nexus.sense.fusion import _app_info_for_pid
            info = _app_info_for_pid(pid)
            return info.get("name", "") if info else ""
        except Exception:
            return ""
    try:
        from AppKit import NSWorkspace
        front = NSWorkspace.sharedWorkspace().frontmostApplication()
        return front.localizedName() if front else ""
    except Exception:
        return ""


def _ensure_loaded():
    """Auto-discover and import recipe modules on first use."""
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        import nexus.via.recipes  # noqa: F401 — triggers __init__.py auto-import
    except Exception:
        pass  # No recipes directory yet — fine
