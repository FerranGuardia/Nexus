"""Intent resolution — the `do` tool.

Parses natural-language-ish intents and routes to the best action.
The AI calls do("click Save") and Nexus figures out the rest.

Supports 60+ intent patterns including click (ordinal, spatial, container),
double/right/triple-click, modifier-click, hover, drag, type, press, scroll
(targeted + until), fill, wait, navigate, js, tab management, and more.
"""

import re
from nexus.act import native, input as raw_input
from nexus.state import emit

# ---------------------------------------------------------------------------
# Re-export everything from submodules for backward compatibility.
# External code (server.py, native.py, tests) can keep importing from here.
# ---------------------------------------------------------------------------

from nexus.act.parse import (  # noqa: F401
    ROLE_MAP, ROLE_WORDS, VERB_SYNONYMS, PHRASE_SYNONYMS,
    ORDINAL_WORDS, ORDINAL_NUM_RE, SPATIAL_RELATIONS, REGION_PATTERNS,
    _CONTAINER_RE, _CONTAINER_ROW_NUM_RE, KEY_ALIASES, _MODIFIER_MAP,
    _normalize_action, _parse_ordinal, _word_to_ordinal, _parse_spatial,
    _filter_by_search, _parse_container, _parse_fields, _strip_quotes,
    _resolve_modifiers,
)

from nexus.act.click import (  # noqa: F401
    _click_spatial, _click_in_region, _click_resolved,
    _click_in_container, _find_and_click_in_row, _click_nth,
    _handle_click, _try_shortcut,
)

from nexus.act.window import (  # noqa: F401
    _handle_tile, _handle_move, _handle_minimize, _handle_restore,
    _handle_resize, _handle_fullscreen, _list_windows,
)

from nexus.act.intents import (  # noqa: F401
    _handle_type, _handle_press, _handle_scroll, _scroll_in_element,
    _scroll_until, _handle_hover, _handle_drag, _handle_fill,
    _handle_wait, _handle_observe, _poll_for,
    _handle_read_table, _handle_read_list,
    _handle_navigate, _handle_path_nav, _handle_run_js, _handle_switch_tab,
    _handle_new_tab, _handle_close_tab, _handle_get_console,
)


# ---------------------------------------------------------------------------
# Router helpers
# ---------------------------------------------------------------------------

def _current_app_name(pid=None):
    """Get the app name for a PID (or frontmost app)."""
    if pid is None:
        from nexus.sense.access import frontmost_app
        info = frontmost_app()
        return info["name"] if info else None
    from nexus.sense.fusion import _app_info_for_pid
    info = _app_info_for_pid(pid)
    return info["name"] if info else None


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

def do(action, pid=None):
    """Execute a natural-language intent.

    Supports action chains: semicolon-separated steps run sequentially.
        do("open Safari; navigate to google.com; wait 1s")

    Args:
        action: Intent string like "click Save", "type hello in search".
            Use semicolons to chain multiple actions.
        pid: Target app PID (default: frontmost app).

    Returns:
        dict with action result (or chain results if multiple steps).
    """
    action = action.strip()
    if not action:
        return {"ok": False, "error": "Empty action"}

    # --- Action chains: "step1; step2; step3" ---
    if ";" in action:
        return _run_chain(action, pid=pid)

    # Check shortcuts BEFORE synonym expansion (so "select all" stays "select all")
    lower = action.lower()

    # --- Shortcut intents ---
    if lower in ("select all", "selectall"):
        raw_input.hotkey("command", "a")
        return {"ok": True, "action": "select_all"}

    if lower in ("copy",):
        raw_input.hotkey("command", "c")
        return {"ok": True, "action": "copy"}

    if lower in ("paste",):
        raw_input.hotkey("command", "v")
        return {"ok": True, "action": "paste"}

    if lower in ("undo",):
        raw_input.hotkey("command", "z")
        return {"ok": True, "action": "undo"}

    if lower in ("redo",):
        raw_input.hotkey("command", "shift", "z")
        return {"ok": True, "action": "redo"}

    if lower in ("close", "close window", "quit", "exit"):
        return native.close_window()

    # --- Getter intents ---
    if lower in ("get clipboard", "read clipboard", "clipboard"):
        return native.clipboard_read()

    if lower in ("get url", "get safari url", "url"):
        return native.safari_url()

    if lower in ("get tabs", "get safari tabs", "tabs", "list tabs"):
        return native.safari_tabs()

    if lower in ("get source", "page source"):
        return native.safari_source()

    if lower in ("get selection", "finder selection", "selected files"):
        return native.finder_selection()

    if lower in ("get console", "console logs", "console", "get logs"):
        return _handle_get_console()

    if lower in ("get table", "read table", "table"):
        return _handle_read_table(pid=pid)

    if lower in ("get list", "read list", "list"):
        return _handle_read_list(pid=pid)

    if lower in ("list recipes", "recipes", "get recipes"):
        from nexus.via.recipe import list_recipes
        recs = list_recipes()
        lines = [f"  {r['name']:30s}  app={r['app'] or 'any':12s}  {r['pattern']}" for r in recs]
        return {"ok": True, "action": "list_recipes",
                "result": f"Registered recipes ({len(recs)}):\n" + "\n".join(lines)}

    # --- Workflow intents ---
    if lower.startswith("record start ") or lower.startswith("record "):
        return _handle_workflow(action, pid=pid)
    if lower in ("record stop", "stop recording"):
        return _handle_workflow(action, pid=pid)
    if lower.startswith("replay "):
        return _handle_workflow(action, pid=pid)
    if lower in ("list workflows", "get workflows", "workflows"):
        return _handle_workflow(action, pid=pid)
    if lower.startswith("delete workflow "):
        return _handle_workflow(action, pid=pid)

    # --- Via intents (learned route recording/replay) ---
    if lower.startswith(("via record ", "via start ")):
        return _handle_via(action, pid=pid)
    if lower in ("via stop", "stop via"):
        return _handle_via(action, pid=pid)
    if lower.startswith(("via replay ", "via run ")):
        return _handle_via(action, pid=pid)
    if lower in ("via list", "list via", "via recordings", "list routes"):
        return _handle_via(action, pid=pid)
    if lower.startswith("via delete "):
        return _handle_via(action, pid=pid)

    # --- Window info getters ---
    if lower in ("list windows", "get windows", "windows", "show windows"):
        return _list_windows()

    if lower.startswith("where is ") or lower.startswith("where's "):
        app_q = action.strip().split(None, 2)[-1].rstrip("?").strip()
        return native.window_info(app_name=app_q)

    if lower in ("window info", "get window info", "get window"):
        return native.window_info()

    # --- Window management shortcuts ---
    if lower in ("maximize", "maximize window"):
        return native.maximize_window()

    if lower in ("fullscreen", "enter fullscreen", "go fullscreen"):
        return native.fullscreen_window()

    if lower in ("exit fullscreen", "leave fullscreen", "unfullscreen"):
        return native.fullscreen_window()  # Toggle

    if lower in ("minimize", "minimize window"):
        return native.minimize_window()

    if lower in ("restore", "restore window", "unminimize", "unminimize window"):
        return native.unminimize_window()

    # --- Action bundles (before synonym expansion — bundles have their own patterns) ---
    from nexus.act.bundles import match_bundle
    handler, bmatch = match_bundle(action)
    if handler:
        return handler(bmatch, pid=pid)

    # --- Synonym expansion (after shortcuts/getters, before verb dispatch) ---
    action = _normalize_action(action)
    lower = action.lower()

    # --- Recipe routing (direct automation before GUI) ---
    from nexus.via.router import route as _try_recipe
    _recipe_result = _try_recipe(action, pid=pid)
    if _recipe_result is not None:
        return _recipe_result

    # --- Verb-based intents ---
    verb, _, rest = action.partition(" ")
    verb = verb.lower()
    rest = rest.strip()

    # Menu paths: "click File > Save" or "menu File > Save"
    if verb in ("click", "menu") and ">" in rest:
        emit(f"Opening menu: {rest}")
        return native.click_menu(rest, pid=pid)

    if verb == "click":
        return _handle_click(rest, pid=pid)

    if verb in ("double-click", "doubleclick", "dblclick"):
        return _handle_click(rest, double=True, pid=pid)

    if verb in ("right-click", "rightclick", "rclick"):
        return _handle_click(rest, right=True, pid=pid)

    if verb in ("triple-click", "tripleclick", "tclick"):
        return _handle_click(rest, triple=True, pid=pid)

    # Modifier-click: "shift-click", "cmd-click", "option-click", "ctrl-click"
    mod_match = re.match(r"^(shift|cmd|command|opt|option|ctrl|control)-?click$", verb, re.IGNORECASE)
    if mod_match:
        return _handle_click(rest, modifiers=[mod_match.group(1).lower()], pid=pid)

    if verb == "type":
        return _handle_type(rest, pid=pid)

    if verb == "press":
        return _handle_press(rest)

    if verb == "open":
        return native.launch_app(rest)

    if verb in ("switch", "activate"):
        target = rest
        if target.lower().startswith("to "):
            target = target[3:]
        # "switch tab 2", "switch to tab Google" → CDP tab switch
        target_stripped = target.strip()
        if target_stripped.lower().startswith("tab"):
            tab_rest = target_stripped[3:].strip()
            return _handle_switch_tab(tab_rest)
        return native.activate_window(app_name=target_stripped)

    if verb == "new" and rest.lower().startswith("tab"):
        tab_rest = rest[3:].strip()
        return _handle_new_tab(tab_rest)

    if verb == "close" and rest.lower().startswith("tab"):
        tab_rest = rest[3:].strip()
        return _handle_close_tab(tab_rest)

    if verb == "scroll":
        return _handle_scroll(rest, pid=pid)

    if verb == "hover":
        return _handle_hover(rest, pid=pid)

    if verb == "focus":
        return native.focus_element(rest, pid=pid)

    if verb == "drag":
        return _handle_drag(rest, pid=pid)

    if verb == "tile":
        return _handle_tile(rest)

    if verb in ("move", "position"):
        return _handle_move(rest)

    if verb == "minimize":
        return _handle_minimize(rest)

    if verb in ("restore", "unminimize"):
        return _handle_restore(rest)

    if verb == "resize":
        return _handle_resize(rest, pid=pid)

    if verb == "fullscreen":
        return _handle_fullscreen(rest)

    if verb == "menu":
        return native.click_menu(rest, pid=pid)

    if verb == "fill":
        return _handle_fill(rest, pid=pid)

    if verb == "wait":
        return _handle_wait(rest, pid=pid)

    if verb == "observe":
        return _handle_observe(rest, pid=pid)

    if verb == "notify":
        return native.notify("Nexus", rest)

    if verb == "say":
        return native.say(rest)

    if verb in ("navigate", "goto", "go"):
        # Path navigation: "navigate General > About" (UI elements, not URLs)
        nav_target = rest
        if nav_target.lower().startswith("to "):
            nav_target = nav_target[3:].strip()
        if ">" in nav_target and not nav_target.startswith(("http://", "https://", "file://")):
            emit(f"Path navigation: {nav_target}")
            return _handle_path_nav(nav_target, pid=pid)
        emit(f"Navigating to {rest}...")
        return _handle_navigate(rest)

    if verb in ("run", "eval", "execute") and rest.lower().startswith("js "):
        return _handle_run_js(rest[3:])

    if verb == "js":
        return _handle_run_js(rest)

    if verb in ("set", "write") and rest.lower().startswith("clipboard "):
        text = rest[10:]  # after "clipboard "
        return native.clipboard_write(_strip_quotes(text))

    # Unknown verb — check for menu path, then try as a click target
    if ">" in action:
        return native.click_menu(action, pid=pid)
    return _handle_click(action, pid=pid)


def _handle_workflow(action, pid=None):
    """Handle workflow recording, replay, and management intents."""
    lower = action.lower().strip()

    if lower in ("record stop", "stop recording"):
        from nexus.mind.workflows import stop_recording
        return stop_recording()

    if lower.startswith("record start "):
        name = action[len("record start "):].strip()
        from nexus.mind.workflows import start_recording
        return start_recording(name)

    if lower.startswith("record ") and lower not in ("record stop",):
        name = action[len("record "):].strip()
        from nexus.mind.workflows import start_recording
        return start_recording(name)

    if lower.startswith("replay "):
        wf_id = action[len("replay "):].strip()
        from nexus.mind.workflows import replay_workflow
        return replay_workflow(wf_id, pid=pid)

    if lower in ("list workflows", "get workflows", "workflows"):
        from nexus.mind.workflows import list_workflows
        wfs = list_workflows()
        if not wfs:
            return {"ok": True, "text": "No workflows recorded. Use do('record start <name>') to start."}
        lines = [f"Workflows ({len(wfs)}):"]
        for wf in wfs:
            lines.append(
                f"  {wf['id']} — {wf['name']} ({wf['step_count']} steps, "
                f"{wf['success_count']} ok / {wf['fail_count']} fail)"
            )
        return {"ok": True, "text": "\n".join(lines)}

    if lower.startswith("delete workflow "):
        wf_id = action[len("delete workflow "):].strip()
        from nexus.mind.workflows import delete_workflow
        deleted = delete_workflow(wf_id)
        if deleted:
            return {"ok": True, "action": "delete_workflow", "id": wf_id}
        return {"ok": False, "error": f'Workflow "{wf_id}" not found'}

    return {"ok": False, "error": f'Unknown workflow command: "{action}"'}


def _handle_via(action, pid=None):
    """Handle Via recording, replay, and management intents."""
    lower = action.lower().strip()

    if lower in ("via stop", "stop via"):
        from nexus.via.recorder import stop_recording
        return stop_recording()

    if lower.startswith(("via record ", "via start ")):
        # Extract name: "via record gmail-login" → "gmail-login"
        name = action.split(None, 2)[-1] if len(action.split()) > 2 else "unnamed"
        from nexus.via.recorder import start_recording
        return start_recording(name)

    if lower.startswith(("via replay ", "via run ")):
        route_id = action.split(None, 2)[-1] if len(action.split()) > 2 else ""
        route_id = route_id.strip()
        from nexus.via.player import replay
        return replay(route_id, pid=pid)

    if lower in ("via list", "list via", "via recordings", "list routes"):
        from nexus.via.recorder import list_recordings
        routes = list_recordings()
        if not routes:
            return {"ok": True, "text": 'No Via routes recorded. Use do("via record <name>") to start.'}
        lines = [f"Via Routes ({len(routes)}):"]
        for r in routes:
            duration = f" ({r['duration_ms'] / 1000:.1f}s)" if r.get("duration_ms") else ""
            lines.append(f"  {r['id']} — {r['name']} ({r['step_count']} steps{duration})")
        return {"ok": True, "text": "\n".join(lines)}

    if lower.startswith("via delete "):
        route_id = action[len("via delete "):].strip()
        from nexus.via.recorder import delete_recording
        deleted = delete_recording(route_id)
        if deleted:
            return {"ok": True, "action": "via_delete", "id": route_id}
        return {"ok": False, "error": f'Via route "{route_id}" not found'}

    return {"ok": False, "error": f'Unknown Via command: "{action}"'}


def _run_chain(action, pid=None):
    """Execute a semicolon-separated chain of actions sequentially.

    Stops at the first failure and reports which step failed.
    After an "open" step, re-resolves PID so subsequent steps target the new app.
    Returns a summary of all completed steps + the failure (if any).
    """
    import time

    steps = [s.strip() for s in action.split(";") if s.strip()]
    if not steps:
        return {"ok": False, "error": "Empty action chain"}

    results = []
    for i, step in enumerate(steps):
        emit(f"Chain {i+1}/{len(steps)}: {step}")
        result = do(step, pid=pid)
        step_summary = {"step": i + 1, "action": step, "ok": result.get("ok", False)}

        if not result.get("ok"):
            step_summary["error"] = result.get("error", "unknown")
            results.append(step_summary)
            return {
                "ok": False,
                "action": "chain",
                "error": f'Step {i + 1} failed: "{step}" — {result.get("error", "unknown")}',
                "completed": i,
                "total": len(steps),
                "steps": results,
            }

        # After "open <app>", re-resolve PID for subsequent steps
        if result.get("ok"):
            normalized = _normalize_action(step.lower())
            step_verb = normalized.split()[0] if normalized else ""
            if step_verb == "open":
                app_name = step.strip().split(None, 1)[1] if len(step.strip().split(None, 1)) > 1 else ""
                if app_name and "." not in app_name and "/" not in app_name:
                    # App launch (not "open file.txt") — update pid
                    new_pid = result.get("pid")
                    if not new_pid:
                        new_pid = native._pid_for_app_name(app_name)
                    if new_pid:
                        pid = new_pid

        results.append(step_summary)
        # Brief pause between steps to let UI settle
        if i < len(steps) - 1:
            time.sleep(0.15)

    return {
        "ok": True,
        "action": "chain",
        "completed": len(steps),
        "total": len(steps),
        "steps": results,
    }
