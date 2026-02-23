"""Self-improving action memory — learns from every do() invocation.

Tracks label translations, action history, and method success rates.
Stored at ~/.nexus/learned.json, separate from the user memory store.

Label learning works by correlating failed and successful actions:
when do("click Save") fails and do("click Guardar") succeeds in the
same app within 30 seconds, the system infers Save → Guardar and
stores the mapping. Next time, do("click Save") succeeds on the
first try via automatic label substitution.
"""

import json
import time as _time
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Storage paths — module-level for test patching (same pattern as store.py)
# ---------------------------------------------------------------------------

LEARN_DIR = Path.home() / ".nexus"
LEARN_FILE = LEARN_DIR / "learned.json"

MAX_ACTIONS = 500          # FIFO ring buffer cap
CORRELATION_WINDOW = 30    # seconds: max gap between fail→succeed to correlate

# Module-level state — loaded once, written on mutation
_store = None
_dirty = False

# Session-level: recent failures awaiting correlation (in-memory only)
_pending_failures = []  # list of {app, verb, target, ts}


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def _ensure_loaded():
    """Load the store from disk if not already loaded."""
    global _store
    if _store is not None:
        return
    _store = _load_from_disk()


def _load_from_disk():
    """Read learned.json, return default structure if missing/corrupt."""
    if not LEARN_FILE.exists():
        return _empty_store()
    try:
        data = json.loads(LEARN_FILE.read_text())
        if not isinstance(data, dict):
            return _empty_store()
        data.setdefault("labels", {})
        data.setdefault("actions", [])
        data.setdefault("methods", {})
        data.setdefault("version", 1)
        return data
    except (json.JSONDecodeError, IOError):
        return _empty_store()


def _empty_store():
    return {"version": 1, "labels": {}, "actions": [], "methods": {}}


def _save():
    """Write the store to disk if dirty."""
    global _dirty
    if not _dirty or _store is None:
        return
    LEARN_DIR.mkdir(parents=True, exist_ok=True)
    LEARN_FILE.write_text(json.dumps(_store, indent=2, ensure_ascii=False))
    _dirty = False


def _mark_dirty():
    global _dirty
    _dirty = True


# ---------------------------------------------------------------------------
# Label translation
# ---------------------------------------------------------------------------

def lookup_label(target, app_name=None):
    """Look up a learned label translation.

    Checks app-specific mapping first, then _global fallback.
    Returns the mapped label string or None.
    """
    _ensure_loaded()
    target_lower = target.lower()
    labels = _store["labels"]

    # App-specific first
    if app_name:
        app_labels = labels.get(app_name.lower(), {})
        if target_lower in app_labels:
            return app_labels[target_lower]["mapped"]

    # Global fallback
    global_labels = labels.get("_global", {})
    if target_lower in global_labels:
        return global_labels[target_lower]["mapped"]

    return None


def record_label(target, mapped, app_name=None):
    """Store a label translation (e.g. Save → Guardar).

    Records both app-specific and _global mappings.
    Increments hit count on repeated observations.
    """
    _ensure_loaded()
    target_lower = target.lower()
    mapped_lower = mapped.lower()

    # Don't record identity mappings
    if target_lower == mapped_lower:
        return

    now = datetime.now().isoformat()
    labels = _store["labels"]

    # App-specific
    if app_name:
        app_key = app_name.lower()
        if app_key not in labels:
            labels[app_key] = {}
        entry = labels[app_key].get(target_lower)
        if entry and entry["mapped"] == mapped_lower:
            entry["hits"] += 1
            entry["updated"] = now
        else:
            labels[app_key][target_lower] = {
                "mapped": mapped_lower, "hits": 1, "updated": now,
            }

    # Global (aggregated across apps)
    if "_global" not in labels:
        labels["_global"] = {}
    g_entry = labels["_global"].get(target_lower)
    if g_entry and g_entry["mapped"] == mapped_lower:
        g_entry["hits"] += 1
        g_entry["updated"] = now
    else:
        labels["_global"][target_lower] = {
            "mapped": mapped_lower, "hits": 1, "updated": now,
        }

    _mark_dirty()
    _save()


# ---------------------------------------------------------------------------
# Session correlation — infer label mappings from fail→succeed patterns
# ---------------------------------------------------------------------------

def record_failure(app_name, verb, target):
    """Record a failed action for later correlation.

    When do("click Save") fails because the element isn't found,
    we store it. If do("click Guardar") succeeds shortly after
    in the same app with the same verb, correlate_success() will
    infer the mapping.
    """
    _pending_failures.append({
        "app": (app_name or "").lower(),
        "verb": verb.lower(),
        "target": target.lower(),
        "ts": _time.time(),
    })
    _prune_old_failures()


def correlate_success(app_name, verb, target):
    """Check if a successful action correlates with a recent failure.

    Returns the original failed target if a correlation was found
    (and records the label mapping), else None.
    """
    now = _time.time()
    app_lower = (app_name or "").lower()
    verb_lower = verb.lower()
    target_lower = target.lower()

    _prune_old_failures()

    # Search backwards (most recent failure first)
    for i in range(len(_pending_failures) - 1, -1, -1):
        f = _pending_failures[i]
        if (f["app"] == app_lower
                and f["verb"] == verb_lower
                and f["target"] != target_lower
                and now - f["ts"] < CORRELATION_WINDOW):
            original = f["target"]
            record_label(original, target_lower, app_name)
            _pending_failures.pop(i)
            return original

    return None


def _prune_old_failures():
    """Remove failures older than the correlation window."""
    cutoff = _time.time() - CORRELATION_WINDOW
    while _pending_failures and _pending_failures[0]["ts"] < cutoff:
        _pending_failures.pop(0)


# ---------------------------------------------------------------------------
# Action history
# ---------------------------------------------------------------------------

def record_action(app_name, intent, ok, verb=None, target=None,
                  method=None, via_label=None):
    """Record an action outcome in the history ring buffer."""
    _ensure_loaded()
    entry = {
        "ts": datetime.now().isoformat(),
        "app": app_name or "",
        "intent": intent,
        "ok": ok,
    }
    if verb:
        entry["verb"] = verb
    if target:
        entry["target"] = target
    if method:
        entry["method"] = method
    if via_label:
        entry["via_label"] = via_label

    _store["actions"].append(entry)

    # FIFO cap
    if len(_store["actions"]) > MAX_ACTIONS:
        _store["actions"] = _store["actions"][-MAX_ACTIONS:]

    # Update method stats per app
    if method and app_name:
        app_key = app_name.lower()
        methods = _store["methods"]
        if app_key not in methods:
            methods[app_key] = {}
        if method not in methods[app_key]:
            methods[app_key][method] = {"ok": 0, "fail": 0}
        methods[app_key][method]["ok" if ok else "fail"] += 1

    _mark_dirty()
    _save()


# ---------------------------------------------------------------------------
# Hints for see() output
# ---------------------------------------------------------------------------

def hints_for_app(app_name):
    """Generate compact learning hints for an app.

    Returns a string to include in see() output, or None if no data.
    """
    _ensure_loaded()
    if not app_name:
        return None

    parts = []
    app_key = app_name.lower()

    # Label translations
    app_labels = _store["labels"].get(app_key, {})
    if app_labels:
        mappings = sorted(app_labels.items(), key=lambda x: -x[1]["hits"])
        pairs = [f"{orig} -> {e['mapped']}" for orig, e in mappings[:5]]
        parts.append("Learned labels: " + ", ".join(pairs))
        if len(mappings) > 5:
            parts.append(f"  ... and {len(mappings) - 5} more")

    # Method preferences
    app_methods = _store["methods"].get(app_key, {})
    if app_methods:
        prefs = []
        for method, counts in app_methods.items():
            total = counts["ok"] + counts["fail"]
            if total >= 3:
                rate = counts["ok"] / total * 100
                prefs.append(f"{method}: {rate:.0f}% ({total} actions)")
        if prefs:
            parts.append("Action methods: " + ", ".join(prefs))

    return "\n".join(parts) if parts else None


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def stats():
    """Summary of what the system has learned."""
    _ensure_loaded()
    label_count = sum(
        len(v) for k, v in _store["labels"].items() if k != "_global"
    )
    global_count = len(_store["labels"].get("_global", {}))
    return {
        "label_mappings": label_count,
        "global_mappings": global_count,
        "actions_recorded": len(_store["actions"]),
        "apps_tracked": len(_store["methods"]),
    }
