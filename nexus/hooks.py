"""Hook pipeline — composable, extensible event system.

Hooks let components influence the pipeline without coupling.
Each hook is a plain function registered with a priority.
Lower priority numbers run first. Stop on {"stop": True}.

Events:
    before_see    — before element tree walk (can inject cached elements)
    after_see     — after elements collected (cache store, dialog info, learning hints)
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
import time as _time
from collections import deque

_hooks = {}  # {event_name: [(priority, name, fn), ...]}
_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Error ring buffer — captures suppressed exceptions for debugging
# ---------------------------------------------------------------------------

_MAX_ERRORS = 20
_error_ring = deque(maxlen=_MAX_ERRORS)


def record_error(source, exc):
    """Record a suppressed exception in the ring buffer.

    Args:
        source: Where the error occurred (e.g. "hook:learning_record", "fusion:see").
        exc: The Exception object.
    """
    _error_ring.append({
        "ts": _time.time(),
        "source": source,
        "error": f"{type(exc).__name__}: {exc}",
    })


def recent_errors(n=20):
    """Return the last N suppressed errors (newest first)."""
    return list(reversed(list(_error_ring)))[:n]


def clear_errors():
    """Clear the error ring buffer."""
    _error_ring.clear()


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
        except Exception as e:
            record_error(f"hook:{_name}", e)  # Capture for debugging

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


def _on_error_skill_suggestion(ctx):
    """on_error: Suggest a CLI alternative from skills when a GUI action fails."""
    try:
        app_name = ctx.get("app_name", "")
        error = ctx.get("error", "")
        if not app_name or "not found" not in error.lower():
            return ctx

        from nexus.mind.skills import find_skill_for_app
        skill_id = find_skill_for_app(app_name)
        if skill_id:
            ctx.setdefault("extra_hints", []).append(
                f"CLI alternative: read skill nexus://skills/{skill_id}"
            )
            ctx["skill_hint"] = f"nexus://skills/{skill_id}"
    except Exception:
        pass
    return ctx


# ---------------------------------------------------------------------------
# Phase 8: Workflow recording hook
# ---------------------------------------------------------------------------


def _workflow_record_hook(ctx):
    """after_do: Record step if workflow recording is active."""
    try:
        from nexus.mind.workflows import is_recording, record_step
        if not is_recording():
            return ctx
        result = ctx.get("result", {})
        if result.get("ok"):
            record_step(ctx.get("action", ""), layout_hash=ctx.get("after_hash"))
    except Exception:
        pass
    return ctx


# ---------------------------------------------------------------------------
# Phase 8: Navigation graph hook
# ---------------------------------------------------------------------------


def _graph_record_hook(ctx):
    """after_do: Record state transition in navigation graph."""
    try:
        before_hash = ctx.get("before_hash")
        after_hash = ctx.get("after_hash")
        if not before_hash or not after_hash or before_hash == after_hash:
            return ctx
        result = ctx.get("result", {})
        if not result.get("ok"):
            return ctx
        from nexus.mind.graph import record_transition
        record_transition(
            before_hash=before_hash,
            after_hash=after_hash,
            action=ctx.get("action", ""),
            app=ctx.get("app_name", ""),
            ok=True,
            elapsed=ctx.get("elapsed", 0),
        )
    except Exception:
        pass
    return ctx


# ---------------------------------------------------------------------------
# Phase 10: Auto-dismiss safe system dialogs
# ---------------------------------------------------------------------------

# Safe dialogs — auto-click the mapped button when auto_dismiss is enabled
_SAFE_DIALOGS = {
    "gatekeeper": "open",
    "folder_permission": "ok",
    "folder_access": "ok",
}

# Unsafe dialogs — always block and inform the agent
_UNSAFE_DIALOGS = {
    "password_prompt",
    "auth_prompt",
    "keychain_access",
    "network_permission",
}


def _button_label_map(button_key):
    """Map button keys to expected label text (including Spanish)."""
    mapping = {
        "open": {"open", "abrir"},
        "ok": {"ok", "aceptar"},
        "cancel": {"cancel", "cancelar"},
        "allow": {"allow", "permitir"},
    }
    return mapping.get(button_key.lower(), {button_key.lower()})


def _click_dialog_button(dialog, classification, button_key):
    """Click a button on a system dialog using OCR or template coordinates."""
    try:
        # Try OCR-based button positions first (pixel-accurate)
        expected = _button_label_map(button_key)
        for btn in classification.get("buttons", []):
            btn_label = btn.get("label", "").lower()
            if btn_label in expected or button_key.lower() in btn_label:
                from nexus.act.input import click

                click(btn["center_x"], btn["center_y"])
                return True

        # Fallback: template relative coordinates
        bounds = dialog.get("bounds", {})
        if not bounds:
            return False

        from nexus.sense.fusion import _ocr_dialog_region
        from nexus.sense.templates import match_template, resolve_button

        ocr_results = _ocr_dialog_region(dialog)
        ocr_text = " ".join(r.get("text", "") for r in ocr_results) if ocr_results else ""
        template_id, template = match_template(ocr_text, dialog.get("process"))
        if template:
            coords = resolve_button(template, button_key, bounds)
            if coords:
                from nexus.act.input import click

                click(coords[0], coords[1])
                return True
    except Exception:
        pass
    return False


def _auto_dismiss_dialog_hook(ctx):
    """before_do: Auto-dismiss safe system dialogs before executing action.

    When auto_dismiss is enabled and a system dialog is blocking:
    - Safe dialogs (Gatekeeper, folder access): auto-click and proceed.
    - Unsafe dialogs (password, keychain): stop with error for agent.
    When auto_dismiss is disabled: detect and add count to ctx only.
    """
    try:
        from nexus.sense.system import detect_system_dialogs, classify_dialog

        dialogs = detect_system_dialogs()
        if not dialogs:
            return ctx

        # Check preference
        from nexus.mind.permissions import _check_auto_dismiss

        if not _check_auto_dismiss():
            # Inform but don't act
            ctx["system_dialogs"] = len(dialogs)
            return ctx

        for dialog in dialogs:
            from nexus.sense.fusion import _ocr_dialog_region

            ocr_results = _ocr_dialog_region(dialog)
            classification = classify_dialog(dialog, ocr_results)
            dialog_type = classification.get("type", "unknown")

            if dialog_type in _UNSAFE_DIALOGS:
                ctx["stop"] = True
                ctx["error"] = (
                    f"System dialog blocking: {classification['description']}. "
                    f"{classification.get('suggested_action', 'User must handle.')} "
                    f"This dialog requires user intervention."
                )
                return ctx

            if dialog_type in _SAFE_DIALOGS:
                button_key = _SAFE_DIALOGS[dialog_type]
                _click_dialog_button(dialog, classification, button_key)
                import time

                time.sleep(0.3)
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
    # OCR fallback moved to perception layer in nexus/sense/plugins.py (Phase 6)
    register("after_see", _system_dialog_hook, priority=60, name="system_dialog")
    register("after_see", _learning_hints_hook, priority=70, name="learning_hints")
    register("before_do", _circuit_breaker_hook, priority=10, name="circuit_breaker")
    register("before_do", _auto_dismiss_dialog_hook, priority=20, name="auto_dismiss")
    register("after_do", _learning_record_hook, priority=10, name="learning_record")
    register("after_do", _journal_record_hook, priority=20, name="journal_record")
    register("after_do", _workflow_record_hook, priority=30, name="workflow_record")
    register("after_do", _graph_record_hook, priority=40, name="graph_record")
    register("on_error", _on_error_skill_suggestion, priority=50, name="skill_suggestion")


# Auto-register on import
register_builtins()
