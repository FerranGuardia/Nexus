"""Nexus Cache — avoid redundant full scans when the screen hasn't changed.

Two storage modes:
  - In-memory (daemon mode): fast, no disk I/O
  - File-based (single-shot mode): persists across invocations via temp file

Cache key = command name + args hash.
Change detection = hash of (window_title + focused_name + element_count) for UIA,
                   hash of (url + title) for web commands.
"""

import hashlib
import json
import os
import time

# Default cache TTL in seconds
DEFAULT_CACHE_TTL = 5.0

# In-memory cache store (for daemon mode)
_mem_cache = {}

# File cache directory
_NEXUS_DATA = os.environ.get("NEXUS_DATA_DIR", r"E:\NexusData")
_CACHE_DIR = os.path.join(_NEXUS_DATA, "cache")


def _ensure_cache_dir():
    os.makedirs(_CACHE_DIR, exist_ok=True)


def _content_hash(result: dict) -> str:
    """Compute a lightweight hash from key fields of a result to detect changes."""
    cmd = result.get("command", "")

    if cmd == "describe":
        win = result.get("window", {})
        focused = result.get("focused_element") or {}
        sig = "%s|%s|%d" % (
            win.get("title", ""),
            focused.get("name", ""),
            result.get("element_count", 0),
        )
    elif cmd in ("web-describe", "web-text", "web-find", "web-links", "web-ax"):
        sig = "%s|%s" % (result.get("url", ""), result.get("title", ""))
    elif cmd == "windows":
        titles = "|".join(w.get("title", "") for w in result.get("windows", []))
        sig = "%s|%d" % (titles, result.get("count", 0))
    else:
        # For other commands, hash the full result
        sig = json.dumps(result, sort_keys=True, ensure_ascii=False)

    return hashlib.md5(sig.encode()).hexdigest()


def _cache_key(command: str, kwargs: dict) -> str:
    """Build a cache key from command name and its arguments."""
    parts = [command]
    for k in sorted(kwargs.keys()):
        v = kwargs[k]
        if v is not None:
            parts.append("%s=%s" % (k, v))
    return "|".join(parts)


def cache_get(command: str, kwargs: dict, ttl: float = DEFAULT_CACHE_TTL, use_file: bool = False) -> dict | None:
    """Check cache for a previous result. Returns the cached result or None.

    If the cache entry exists and is within TTL, returns:
      {"changed": False, "cached_at": timestamp, "age": seconds}
    """
    key = _cache_key(command, kwargs)

    if use_file:
        return _file_cache_get(key, ttl)
    else:
        return _mem_cache_get(key, ttl)


def cache_put(command: str, kwargs: dict, result: dict, use_file: bool = False):
    """Store a result in the cache."""
    key = _cache_key(command, kwargs)
    entry = {
        "result": result,
        "hash": _content_hash(result),
        "timestamp": time.time(),
    }

    if use_file:
        _file_cache_put(key, entry)
    else:
        _mem_cache[key] = entry


def cache_clear():
    """Clear all cached entries (both memory and file)."""
    _mem_cache.clear()
    if os.path.exists(_CACHE_DIR):
        for f in os.listdir(_CACHE_DIR):
            try:
                os.remove(os.path.join(_CACHE_DIR, f))
            except OSError:
                pass


# ---------------------------------------------------------------------------
# In-memory cache (daemon mode)
# ---------------------------------------------------------------------------

def _mem_cache_get(key: str, ttl: float) -> dict | None:
    entry = _mem_cache.get(key)
    if not entry:
        return None
    age = time.time() - entry["timestamp"]
    if age > ttl:
        del _mem_cache[key]
        return None
    return {
        "command": entry["result"].get("command", ""),
        "changed": False,
        "cached_at": entry["timestamp"],
        "age": round(age, 2),
        "hash": entry["hash"],
    }


# ---------------------------------------------------------------------------
# File-based cache (single-shot mode)
# ---------------------------------------------------------------------------

def _file_key_to_path(key: str) -> str:
    h = hashlib.md5(key.encode()).hexdigest()
    return os.path.join(_CACHE_DIR, "%s.json" % h)


def _file_cache_get(key: str, ttl: float) -> dict | None:
    path = _file_key_to_path(key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            entry = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    age = time.time() - entry.get("timestamp", 0)
    if age > ttl:
        try:
            os.remove(path)
        except OSError:
            pass
        return None
    return {
        "command": entry.get("result", {}).get("command", ""),
        "changed": False,
        "cached_at": entry["timestamp"],
        "age": round(age, 2),
        "hash": entry["hash"],
    }


def _file_cache_put(key: str, entry: dict):
    _ensure_cache_dir()
    path = _file_key_to_path(key)
    try:
        with open(path, "w") as f:
            json.dump(entry, f)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Diff computation — element-level changes between cached and fresh results
# ---------------------------------------------------------------------------

def _element_key(el: dict) -> str:
    """Unique key for an element: name + type (role)."""
    return "%s|%s" % (el.get("name", ""), el.get("type", el.get("role", "")))


def compute_diff(old_result: dict, new_result: dict) -> dict:
    """Compute element-level diff between two describe/web-ax results.

    Returns:
        {"mode": "diff", "added": [...], "removed": [...], "changed": [...],
         "unchanged_count": int, "summary": str}
    """
    cmd = new_result.get("command", "")

    # Extract element lists based on command type
    if cmd == "describe":
        old_elements = old_result.get("elements", [])
        new_elements = new_result.get("elements", [])
    elif cmd == "web-ax":
        old_elements = old_result.get("nodes", [])
        new_elements = new_result.get("nodes", [])
    else:
        return {"mode": "diff", "error": "Diff not supported for command '%s'" % cmd}

    # Build lookup by key
    old_by_key = {}
    for el in old_elements:
        k = _element_key(el)
        old_by_key[k] = el

    new_by_key = {}
    for el in new_elements:
        k = _element_key(el)
        new_by_key[k] = el

    old_keys = set(old_by_key.keys())
    new_keys = set(new_by_key.keys())

    added = [new_by_key[k] for k in (new_keys - old_keys)]
    removed = [old_by_key[k] for k in (old_keys - new_keys)]

    # Detect property changes in shared elements
    changed = []
    unchanged_count = 0
    for k in (old_keys & new_keys):
        old_el = old_by_key[k]
        new_el = new_by_key[k]
        changes = _element_changes(old_el, new_el)
        if changes:
            changed.append({
                "name": new_el.get("name", ""),
                "type": new_el.get("type", new_el.get("role", "")),
                "changes": changes,
            })
        else:
            unchanged_count += 1

    # Build summary
    parts = []
    if added:
        parts.append("%d new" % len(added))
    if removed:
        parts.append("%d removed" % len(removed))
    if changed:
        parts.append("%d changed" % len(changed))
    parts.append("%d unchanged" % unchanged_count)

    # Detect semantic events
    events = _detect_events(old_result, new_result, added, removed, changed)
    if events:
        parts.extend(events)

    old_ts = old_result.get("_cached_at", 0)
    age = round(time.time() - old_ts, 1) if old_ts else 0

    return {
        "command": cmd,
        "mode": "diff",
        "since_seconds": age,
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged_count": unchanged_count,
        "summary": ". ".join(parts) + ".",
        "window": new_result.get("window", new_result.get("title", "")),
    }


def _element_changes(old: dict, new: dict) -> dict:
    """Compare two element dicts, return dict of changed fields {field: [old, new]}."""
    changes = {}
    # Check properties that matter
    check_fields = ["focused", "disabled", "is_enabled", "expanded", "checked"]
    for field in check_fields:
        if field in old or field in new:
            ov = old.get(field)
            nv = new.get(field)
            if ov != nv:
                changes[field] = [ov, nv]

    # Check if bounds moved significantly (>20px)
    old_bounds = old.get("bounds", {})
    new_bounds = new.get("bounds", {})
    if old_bounds and new_bounds:
        old_cx = old_bounds.get("center_x", old_bounds.get("x", 0))
        new_cx = new_bounds.get("center_x", new_bounds.get("x", 0))
        old_cy = old_bounds.get("center_y", old_bounds.get("y", 0))
        new_cy = new_bounds.get("center_y", new_bounds.get("y", 0))
        if abs(old_cx - new_cx) > 20 or abs(old_cy - new_cy) > 20:
            changes["position"] = [
                "(%d,%d)" % (old_cx, old_cy),
                "(%d,%d)" % (new_cx, new_cy),
            ]

    return changes


def _detect_events(old_result: dict, new_result: dict,
                   added: list, removed: list, changed: list) -> list[str]:
    """Detect semantic events from the diff."""
    events = []

    # Focus change
    old_focus = (old_result.get("focused_element") or {}).get("name", "")
    new_focus = (new_result.get("focused_element") or {}).get("name", "")
    if old_focus != new_focus and new_focus:
        events.append("Focus: %s → %s" % (old_focus or "(none)", new_focus))

    # Dialog appeared (new element with Dialog/Window type or "dialog" role)
    dialog_types = {"WindowControl", "PaneControl", "dialog", "alertdialog"}
    new_dialogs = [el for el in added
                   if el.get("type", el.get("role", "")) in dialog_types]
    if new_dialogs:
        names = [d.get("name", "?") for d in new_dialogs]
        events.append("Dialog appeared: %s" % ", ".join(names))

    # Error appeared
    for el in added:
        name_lower = el.get("name", "").lower()
        if any(kw in name_lower for kw in ("error", "warning", "alert", "fail")):
            events.append("Error: '%s'" % el.get("name", ""))
            break

    return events


def cache_get_for_diff(command: str, kwargs: dict, use_file: bool = False) -> dict | None:
    """Get the full cached result for diff computation (not just the cache-hit response).

    Returns the stored result dict with _cached_at timestamp, or None.
    """
    key = _cache_key(command, kwargs)

    if use_file:
        path = _file_key_to_path(key)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r") as f:
                entry = json.load(f)
            result = entry.get("result", {})
            result["_cached_at"] = entry.get("timestamp", 0)
            return result
        except (json.JSONDecodeError, OSError):
            return None
    else:
        entry = _mem_cache.get(key)
        if not entry:
            return None
        result = entry["result"].copy()
        result["_cached_at"] = entry["timestamp"]
        return result
