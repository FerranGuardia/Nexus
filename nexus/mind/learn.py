"""Self-improving action memory — learns from every do() invocation.

Tracks label translations, action history, and method success rates.
Stored in SQLite via db.py (~/.nexus/nexus.db).

Label learning works by correlating failed and successful actions:
when do("click Save") fails and do("click Guardar") succeeds in the
same app within 30 seconds, the system infers Save → Guardar and
stores the mapping. Next time, do("click Save") succeeds on the
first try via automatic label substitution.
"""

import time as _time
from datetime import datetime

MAX_ACTIONS = 500          # FIFO ring buffer cap
CORRELATION_WINDOW = 30    # seconds: max gap between fail→succeed to correlate

# Session-level: recent failures awaiting correlation (in-memory only)
_pending_failures = []  # list of {app, verb, target, ts}


# ---------------------------------------------------------------------------
# Label translation
# ---------------------------------------------------------------------------

def lookup_label(target, app_name=None):
    """Look up a learned label translation.

    Checks app-specific mapping first, then _global fallback.
    Returns the mapped label string or None.
    """
    from nexus.mind.db import label_get
    target_lower = target.lower()

    # App-specific first
    if app_name:
        entry = label_get(app_name.lower(), target_lower)
        if entry:
            return entry["mapped"]

    # Global fallback
    entry = label_get("_global", target_lower)
    if entry:
        return entry["mapped"]

    return None


def record_label(target, mapped, app_name=None):
    """Store a label translation (e.g. Save → Guardar).

    Records both app-specific and _global mappings.
    Increments hit count on repeated observations.
    """
    from nexus.mind.db import label_upsert
    target_lower = target.lower()
    mapped_lower = mapped.lower()

    # Don't record identity mappings
    if target_lower == mapped_lower:
        return

    # App-specific
    if app_name:
        label_upsert(app_name.lower(), target_lower, mapped_lower)

    # Global (aggregated across apps)
    label_upsert("_global", target_lower, mapped_lower)


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
    from nexus.mind.db import action_insert, action_count, action_trim, method_upsert

    action_insert(
        ts=datetime.now().isoformat(),
        app=app_name or "",
        intent=intent,
        ok=ok,
        verb=verb,
        target=target,
        method=method,
        via_label=via_label,
    )

    # FIFO cap
    if action_count() > MAX_ACTIONS:
        action_trim(MAX_ACTIONS)

    # Update method stats per app
    if method and app_name:
        method_upsert(app_name.lower(), method, ok)


# ---------------------------------------------------------------------------
# Hints for see() output
# ---------------------------------------------------------------------------

def hints_for_app(app_name):
    """Generate compact learning hints for an app.

    Returns a string to include in see() output, or None if no data.
    """
    from nexus.mind.db import label_get_all_for_app, method_stats_for_app

    if not app_name:
        return None

    parts = []
    app_key = app_name.lower()

    # Label translations
    app_labels = label_get_all_for_app(app_key)
    if app_labels:
        pairs = [f"{e['target']} -> {e['mapped']}" for e in app_labels[:5]]
        parts.append("Learned labels: " + ", ".join(pairs))
        if len(app_labels) > 5:
            parts.append(f"  ... and {len(app_labels) - 5} more")

    # Method preferences
    app_methods = method_stats_for_app(app_key)
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
    from nexus.mind.db import label_count, action_count, method_app_count
    return {
        "label_mappings": label_count(exclude_global=True),
        "global_mappings": label_count(global_only=True),
        "actions_recorded": action_count(),
        "apps_tracked": method_app_count(),
    }
