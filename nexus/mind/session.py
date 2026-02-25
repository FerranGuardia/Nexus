"""Session state — in-memory cache and journal for the current server lifetime.

Tracks spatial cache (element layouts with structural change detection),
action journal (proprioception), and request metadata. All state is
in-memory only — lost on server restart, which is fine.

No disk I/O. No persistence. Just fast in-process state.
"""

import hashlib
import threading
import time
from collections import deque


# ---------------------------------------------------------------------------
# Spatial cache — longer-lived element cache (3s TTL) above tree cache (1s)
# ---------------------------------------------------------------------------

_spatial_cache = {}   # {pid: {"elements": [...], "hash": str, "ts": float,
                      #        "dirty": bool, "max_elements": int}}
_SPATIAL_TTL = 3.0
_MAX_CACHED_PIDS = 10
_spatial_lock = threading.Lock()

# Stats counters
_spatial_hits = 0
_spatial_misses = 0


def spatial_get(pid, max_elements=150):
    """Get cached elements for a PID if fresh and not dirty.

    Returns (elements, layout_hash) on hit, (None, None) on miss.
    """
    global _spatial_hits, _spatial_misses

    if pid is None:
        _spatial_misses += 1
        return None, None

    with _spatial_lock:
        entry = _spatial_cache.get(pid)
        if entry is None:
            _spatial_misses += 1
            return None, None

        # Stale?
        if time.time() - entry["ts"] >= _SPATIAL_TTL:
            _spatial_misses += 1
            return None, None

        # Dirty from observer event?
        if entry["dirty"]:
            _spatial_misses += 1
            return None, None

        # max_elements mismatch? Return None to avoid serving truncated data
        if entry["max_elements"] != max_elements:
            _spatial_misses += 1
            return None, None

        _spatial_hits += 1
        return entry["elements"], entry["hash"]


def spatial_put(pid, elements, max_elements=150):
    """Store elements in spatial cache with computed layout hash.

    Strips _ref keys (AX element references go stale between calls).
    Keeps _ax_role and _group (plain strings needed for filtering).

    Returns the computed layout_hash.
    """
    if pid is None or not elements:
        return ""

    # Strip _ref (stale AX refs cause crashes), keep everything else
    clean = [
        {k: v for k, v in el.items() if k != "_ref"}
        for el in elements
    ]

    layout_hash = compute_layout_hash(elements)

    with _spatial_lock:
        _spatial_cache[pid] = {
            "elements": clean,
            "hash": layout_hash,
            "ts": time.time(),
            "dirty": False,
            "max_elements": max_elements,
        }
        _evict_oldest()

    return layout_hash


def mark_dirty(pid=None):
    """Mark a PID's spatial cache as dirty (or all PIDs if None).

    Called by observe.py when AXObserver events fire, and by
    intents.py after path navigation invalidates the tree.
    """
    with _spatial_lock:
        if pid is None:
            for entry in _spatial_cache.values():
                entry["dirty"] = True
        elif pid in _spatial_cache:
            _spatial_cache[pid]["dirty"] = True


def compute_layout_hash(elements):
    """Compute structural fingerprint from element roles + labels.

    Includes role + label (structural identity).
    Excludes value, pos, enabled (volatile state).

    Returns 12-char hex string.
    """
    parts = sorted(
        (el.get("_ax_role", el.get("role", "")), el.get("label", ""))
        for el in elements
    )
    raw = "|".join(f"{r}:{l}" for r, l in parts)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def spatial_stats():
    """Return spatial cache stats for diagnostics."""
    with _spatial_lock:
        return {
            "cached_pids": len(_spatial_cache),
            "hits": _spatial_hits,
            "misses": _spatial_misses,
        }


def _evict_oldest():
    """Remove the oldest cache entry if over capacity. Must hold _spatial_lock."""
    if len(_spatial_cache) > _MAX_CACHED_PIDS:
        oldest_pid = min(_spatial_cache, key=lambda p: _spatial_cache[p]["ts"])
        del _spatial_cache[oldest_pid]


# ---------------------------------------------------------------------------
# Action journal — compact proprioception for do() responses
# ---------------------------------------------------------------------------

_journal = deque(maxlen=50)


def journal_record(action, app, ok, elapsed=0, error="", changes=""):
    """Append an action to the session journal."""
    _journal.append({
        "ts": time.time(),
        "action": action,
        "app": app,
        "ok": ok,
        "elapsed": elapsed,
        "error": error,
        "changes": changes,
    })


def journal_recent(n=5):
    """Return the last n journal entries as a compact text string.

    Format per line: "{age}: {action} -> {status}[, {change_hint}] ({app})"
    Returns empty string if journal is empty or n <= 0.
    """
    if not _journal or n <= 0:
        return ""

    now = time.time()
    entries = list(_journal)[-n:]
    lines = []

    for entry in entries:
        age = now - entry["ts"]
        if age < 60:
            age_str = f"{int(age)}s ago"
        else:
            age_str = f"{int(age / 60)}m ago"

        status = "OK" if entry["ok"] else "FAIL"

        # Truncate action to 30 chars
        action = entry["action"]
        if len(action) > 30:
            action = action[:27] + "..."

        # Extract key change info (first meaningful line, 40 char max)
        change_hint = ""
        if entry.get("changes"):
            first_line = entry["changes"].split("\n")[0]
            if len(first_line) > 40:
                first_line = first_line[:37] + "..."
            change_hint = f", {first_line}"

        error_hint = ""
        if not entry["ok"] and entry.get("error"):
            err = entry["error"]
            if len(err) > 30:
                err = err[:27] + "..."
            error_hint = f": {err}"

        app = entry.get("app", "")
        app_part = f" ({app})" if app else ""

        lines.append(f"{age_str}: {action} -> {status}{error_hint}{change_hint}{app_part}")

    return "\n".join(lines)


def journal_entries(n=50):
    """Return raw journal entries (for diagnostics/testing)."""
    return list(_journal)[-n:]


# ---------------------------------------------------------------------------
# Session metadata
# ---------------------------------------------------------------------------

_session_start = time.time()
_request_count = 0


def tick():
    """Increment request counter. Called on every MCP tool invocation."""
    global _request_count
    _request_count += 1


def session_info():
    """Return session summary (uptime, request count, cache stats)."""
    stats = spatial_stats()
    return {
        "uptime": round(time.time() - _session_start, 1),
        "requests": _request_count,
        "spatial_cached_pids": stats["cached_pids"],
        "spatial_hits": stats["hits"],
        "spatial_misses": stats["misses"],
        "journal_entries": len(_journal),
    }


def reset():
    """Clear all session state. For testing only."""
    global _spatial_hits, _spatial_misses, _request_count, _session_start

    with _spatial_lock:
        _spatial_cache.clear()
    _journal.clear()
    _spatial_hits = 0
    _spatial_misses = 0
    _request_count = 0
    _session_start = time.time()
