"""Hook pipeline — composable, extensible event system.

Hooks let components influence the pipeline without coupling.
Each hook is a plain function registered with a priority.
Lower priority numbers run first. Stop on {"stop": True}.

Events:
    before_see    — before element tree walk (can inject cached elements)
    after_see     — after elements collected (OCR fallback, cache store, etc.)
    before_do     — before action dispatch (future: shortcuts, label sub)
    after_do      — after action result (learning, journal recording)
    on_error      — when do() fails (future: retry with fallbacks)
    on_app_switch — when focused app changes (future: pre-fetch, skills)
    on_system_dialog — when system dialog detected (future: auto-handle)

Context conventions:
    before_see: {pid, query, app_info, fetch_limit}
        → hooks can set: cached_elements, layout_hash
    after_see:  {pid, elements, app_info, result_parts, query, fetch_limit}
        → hooks mutate result_parts (mutable list) in place
    after_do:   {action, pid, result, app_name, elapsed, changes, verb, target, app_param}
        → hooks trigger side effects (recording, learning)
"""

import threading

_hooks = {}  # {event_name: [(priority, name, fn), ...]}
_lock = threading.Lock()


def register(event, fn, priority=50, name=None):
    """Register a hook function for an event.

    Args:
        event: Event name (e.g. "before_see", "after_do").
        fn: Callable(ctx) -> ctx or None.
        priority: Lower runs first (default 50).
        name: Optional human-readable name (for debugging/listing).
    """
    hook_name = name or getattr(fn, "__name__", "anonymous")
    with _lock:
        if event not in _hooks:
            _hooks[event] = []
        _hooks[event].append((priority, hook_name, fn))
        _hooks[event].sort(key=lambda h: h[0])


def fire(event, ctx):
    """Fire all hooks for an event, passing context dict through.

    Each hook receives ctx and returns a (possibly modified) ctx.
    If a hook returns None, the original ctx continues unchanged.
    If a hook returns {"stop": True, ...}, processing halts.
    Every hook is wrapped in try/except — a broken hook never
    breaks the pipeline.

    Returns the final ctx dict.
    """
    with _lock:
        hooks = list(_hooks.get(event, []))

    for _priority, _name, fn in hooks:
        try:
            result = fn(ctx)
            if result is not None:
                if result.get("stop"):
                    return result
                ctx = result
        except Exception:
            pass  # Hooks must never break the pipeline

    return ctx


def clear(event=None):
    """Clear hooks. If event is None, clear all."""
    with _lock:
        if event is None:
            _hooks.clear()
        else:
            _hooks.pop(event, None)


def registered(event=None):
    """List registered hooks for debugging.

    Returns dict {event: [(priority, name), ...]} or list for a specific event.
    """
    with _lock:
        if event is not None:
            return [(p, n) for p, n, _ in _hooks.get(event, [])]
        return {
            ev: [(p, n) for p, n, _ in hooks]
            for ev, hooks in _hooks.items()
        }


# ---------------------------------------------------------------------------
# Built-in hooks — wrap existing behaviors as composable pipeline steps
# ---------------------------------------------------------------------------


def _spatial_cache_read(ctx):
    """before_see: Check spatial cache for cached elements."""
    try:
        from nexus.mind.session import spatial_get
        pid = ctx.get("pid")
        fetch_limit = ctx.get("fetch_limit", 150)
        cached, layout_hash = spatial_get(pid, fetch_limit)
        if cached is not None:
            ctx["cached_elements"] = cached
            ctx["layout_hash"] = layout_hash
    except Exception:
        pass
    return ctx


def _spatial_cache_write(ctx):
    """after_see: Store elements in spatial cache."""
    try:
        from nexus.mind.session import spatial_put
        pid = ctx.get("pid")
        elements = ctx.get("elements")
        fetch_limit = ctx.get("fetch_limit", 150)
        if elements and not ctx.get("from_cache"):
            spatial_put(pid, elements, fetch_limit)
    except Exception:
        pass
    return ctx


def _ocr_fallback_hook(ctx):
    """after_see: Run OCR when AX tree has too few labeled elements."""
    if ctx.get("query"):
        return ctx  # Skip OCR in search mode

    elements = ctx.get("elements", [])
    labeled_count = sum(1 for el in elements if el.get("label"))
    if labeled_count >= 5:
        return ctx

    try:
        from nexus.sense.fusion import _ocr_fallback
        pid = ctx.get("pid")
        app_info = ctx.get("app_info")
        ocr_elements = _ocr_fallback(pid, app_info)
        if ocr_elements:
            result_parts = ctx.get("result_parts", [])
            result_parts.append("")
            result_parts.append(f"OCR Fallback ({len(ocr_elements)} text regions):")
            for el in ocr_elements[:30]:
                conf = el.get("confidence", 0)
                result_parts.append(
                    f'  [text (OCR)] "{el["label"]}" @ {el["pos"][0]},{el["pos"][1]} ({conf:.0%})'
                )
            if len(ocr_elements) > 30:
                result_parts.append(f"  ... and {len(ocr_elements) - 30} more")
    except Exception:
        pass
    return ctx


def _system_dialog_hook(ctx):
    """after_see: Detect system dialogs (Gatekeeper, SecurityAgent, etc.)."""
    try:
        from nexus.sense.fusion import _detect_system_dialogs
        text = _detect_system_dialogs()
        if text:
            result_parts = ctx.get("result_parts", [])
            result_parts.append("")
            result_parts.append(text)
    except Exception:
        pass
    return ctx


def _learning_hints_hook(ctx):
    """after_see: Show learned labels for the current app."""
    app_info = ctx.get("app_info")
    if not app_info:
        return ctx
    try:
        from nexus.mind.learn import hints_for_app
        hints = hints_for_app(app_info.get("name", ""))
        if hints:
            result_parts = ctx.get("result_parts", [])
            result_parts.append("")
            result_parts.append("Learned:")
            for line in hints.split("\n"):
                result_parts.append(f"  {line}")
    except Exception:
        pass
    return ctx


def _circuit_breaker_hook(ctx):
    """before_do: Stop after consecutive failures to prevent blind retries.

    Checks the session journal for recent failures. If 3+ consecutive
    failures happened in the same app within 30 seconds, returns a stop
    signal with a clear error instead of letting the agent keep clicking.
    Resets on any success.
    """
    try:
        from nexus.mind.session import journal_entries
        import time

        entries = journal_entries(10)
        if not entries:
            return ctx

        now = time.time()
        consecutive_fails = 0
        fail_actions = []

        # Walk backwards through journal
        for entry in reversed(entries):
            age = now - entry["ts"]
            if age > 30:
                break  # Only look at last 30 seconds
            if entry["ok"]:
                break  # Any success resets the streak
            consecutive_fails += 1
            action = entry.get("action", "?")
            if len(action) > 40:
                action = action[:37] + "..."
            fail_actions.append(action)

        if consecutive_fails >= 3:
            app = entries[-1].get("app", "this app")
            ctx["stop"] = True
            ctx["error"] = (
                f"Circuit breaker: {consecutive_fails} consecutive failures "
                f"on {app} in the last 30s. Stopping to prevent unintended "
                f"actions.\n"
                f"Failed actions: {', '.join(reversed(fail_actions))}\n"
                f"Suggestion: try a different approach, use see() to check "
                f"the current state, or ask the user for help."
            )
    except Exception:
        pass
    return ctx


def _learning_record_hook(ctx):
    """after_do: Record action outcome for learning."""
    try:
        from nexus.mind.learn import record_action, record_failure, correlate_success
        result = ctx.get("result", {})
        app_name = ctx.get("app_name", "")
        verb = ctx.get("verb", "")
        target = ctx.get("target", "")
        action = ctx.get("action", "")

        if result.get("ok"):
            correlated = correlate_success(app_name, verb, target)
            record_action(
                app_name=app_name, intent=action, ok=True,
                verb=verb, target=target,
                method=result.get("action"),
                via_label=result.get("via_label") or (target if correlated else None),
            )
        else:
            if "not found" in result.get("error", "").lower():
                record_failure(app_name, verb, target)
            record_action(
                app_name=app_name, intent=action, ok=False,
                verb=verb, target=target,
            )
    except Exception:
        pass
    return ctx


def _journal_record_hook(ctx):
    """after_do: Record action in session journal."""
    try:
        from nexus.mind.session import journal_record
        journal_record(
            action=ctx.get("action", ""),
            app=ctx.get("app_name", ""),
            ok=ctx.get("result", {}).get("ok", False),
            elapsed=ctx.get("elapsed", 0),
            error=ctx.get("result", {}).get("error", ""),
            changes=ctx.get("changes", ""),
        )
    except Exception:
        pass
    return ctx


# ---------------------------------------------------------------------------
# Bootstrap — register all built-in hooks
# ---------------------------------------------------------------------------


def register_builtins():
    """Register all built-in hooks. Safe to call multiple times."""
    register("before_see", _spatial_cache_read, priority=10, name="spatial_cache_read")
    register("after_see", _spatial_cache_write, priority=10, name="spatial_cache_write")
    register("after_see", _ocr_fallback_hook, priority=50, name="ocr_fallback")
    register("after_see", _system_dialog_hook, priority=60, name="system_dialog")
    register("after_see", _learning_hints_hook, priority=70, name="learning_hints")
    register("before_do", _circuit_breaker_hook, priority=10, name="circuit_breaker")
    register("after_do", _learning_record_hook, priority=10, name="learning_record")
    register("after_do", _journal_record_hook, priority=20, name="journal_record")


# Auto-register on import
register_builtins()
