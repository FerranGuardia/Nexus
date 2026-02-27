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

# Partitioned index: {app_key: [Recipe]} and None for global recipes.
# Rebuilt on registration. Avoids scanning all 41+ recipes on every do().
_by_app: dict[str | None, list[Recipe]] = {}
_partitioned: bool = False


def _rebuild_partition():
    """Rebuild the app-partitioned index from the registry."""
    global _partitioned
    _by_app.clear()
    for r in _registry:
        _by_app.setdefault(r.app, []).append(r)
    _partitioned = True


def recipe(pattern, app=None, priority=50):
    """Decorator to register an intent recipe."""
    global _partitioned
    compiled = re.compile(pattern, re.IGNORECASE)

    def decorator(fn):
        global _partitioned
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
                _partitioned = False  # Invalidate partition
                return fn
        _registry.append(r)
        _registry.sort(key=lambda x: x.priority)
        _partitioned = False  # Invalidate partition
        return fn

    return decorator


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def match_recipe(action, pid=None, app_name=None):
    """Find first matching recipe for this action.

    Args:
        action: Intent string to match against recipes.
        pid: Process ID (used to determine app if app_name not given).
        app_name: App name (avoids redundant ObjC call if caller knows it).

    Returns (Recipe, re.Match) or (None, None).
    """
    _ensure_loaded()
    if not _partitioned:
        _rebuild_partition()

    if app_name is None:
        app_name = _current_app(pid)

    app_lower = app_name.lower() if app_name else ""

    # Check app-specific recipes first, then global
    candidates = []
    if app_lower:
        for app_key, recipes in _by_app.items():
            if app_key and app_key in app_lower:
                candidates.extend(recipes)
    # Always include global recipes (app=None)
    candidates.extend(_by_app.get(None, []))
    # Sort by priority (partitions may interleave)
    candidates.sort(key=lambda r: r.priority)

    for r in candidates:
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
