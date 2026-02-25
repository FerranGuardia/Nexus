"""Nexus MCP Server — Three tools to see and control your Mac.

    see     →  Unified perception (accessibility tree + windows + screenshot)
    do      →  Intent-based actions ("click Save", "type hello", "open Safari")
    memory  →  Persistent key-value store across sessions

That's it. Three tools. The AI doesn't need to know about
AXUIElement vs CGWindow vs AppleScript. It just sees and does.
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "Nexus",
    instructions=(
        "Nexus gives you eyes and hands on a Mac. "
        "Use `see` first to understand what's on screen, "
        "then `do` to act on it. "
        "Use `memory` to remember things across sessions.\n\n"
        "IMPORTANT: Nexus is for GUI interaction only — clicking, typing, window management, "
        "and controlling apps that have no API or CLI. "
        "If you already have tools that can fetch web pages, read files, run shell commands, "
        "or call APIs — use THOSE instead. Don't use Nexus to read web content when you can "
        "fetch the URL directly. Don't use `see` to read a file when you have a file reader. "
        "Use `do('get url')` to discover what's in the browser, then fetch it yourself. "
        "Nexus is the physical layer — only use it for what you literally cannot do without it.\n\n"
        "SKILLS: Nexus has CLI skills for common tasks (email, GitHub, etc.). "
        "Before using see/do for a task, check the `nexus://skills` resource to see if "
        "a faster CLI-based approach exists. Read a skill with `nexus://skills/{id}` "
        "to get the exact commands. Skills are just knowledge — you run the CLI commands yourself."
    ),
)


@mcp.tool(
    annotations={
        "title": "See",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
def see(
    app: str | None = None,
    query: str | None = None,
    screenshot: bool = False,
    menus: bool = False,
    diff: bool = False,
    content: bool = False,
    observe: bool = False,
) -> str | list:
    """See what's on screen right now.

    Returns the focused app, window list, focused element, and all
    interactive elements in the accessibility tree. This is your eyes.

    Args:
        app: Look at a specific app by name (default: frontmost app).
        query: Search for specific elements instead of full tree.
        screenshot: Include a screenshot (adds ~50KB, use sparingly).
        menus: Include the app's menu bar (shows all available commands + shortcuts).
        diff: Compare with previous snapshot — show what changed since last see().
        content: Include text content from documents, text areas, and fields.
            Shows what's written in the app, not just the UI chrome.
        observe: Start observing this app for changes. Events are buffered
            and included in subsequent see() calls automatically.

    Call this first to understand what the user sees.
    For apps with many elements, use query= to search instead of browsing the full tree.
    When Chrome is focused, `see` includes web page content via CDP.
    """
    from nexus.sense.fusion import see as _see, _resolve_pid
    from nexus.state import start_action, end_action, emit

    try:
        from nexus.mind.session import tick
        tick()
    except Exception:
        pass

    # Normalize: FastMCP may pass "" instead of None for unspecified params
    app = app.strip() if isinstance(app, str) and app.strip() else None

    # Resolve app name to PID at server level (avoids MCP parameter passing issues)
    pid = _resolve_pid(app) if app else None
    desc = f"query={query}" if query else "full tree"
    if screenshot:
        desc += " +screenshot"
    if menus:
        desc += " +menus"
    start_action("see", desc, app=app or "")
    emit(f"Building perception for {app or 'frontmost'}...")
    result = _see(app=pid, query=query, screenshot=screenshot, menus=menus, diff=diff, content=content, observe=observe)
    end_action("done")

    # If screenshot requested, return multimodal content
    if result.get("image"):
        from mcp.types import TextContent, ImageContent
        return [
            TextContent(type="text", text=result["text"]),
            ImageContent(type="image", data=result["image"], mimeType="image/jpeg"),
        ]

    return result["text"]


@mcp.tool(
    annotations={
        "title": "Do",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    }
)
def do(action: str, app: str | None = None) -> str:
    """Execute an action on the computer.

    Verb-first intent format. Nexus finds the best way to execute it
    (accessibility actions, AppleScript, or keyboard/mouse).

    Args:
        action: Intent string like "click Save", "type hello in search".
            Use semicolons to chain actions: "open Safari; navigate to google.com; wait 1s"
        app: Target app by name (default: frontmost). Use this to act on
             background apps without switching focus.

    Supported intents:
        click <target>           - Find & click element by name
        click <File > Save>      - Click a menu item by path
        click the 2nd <role>     - Click by ordinal (1st, 2nd, last...)
        click <role> near <ref>  - Click element nearest to a reference
        click <role> below <ref> - Click element below a reference (also: above, left of, right of)
        click <role> in <region> - Click element in screen region (top-right, bottom-left, center...)
        shift-click <target>     - Click while holding Shift (multi-select)
        cmd-click <target>       - Click while holding Command
        option-click <target>    - Click while holding Option
        double-click <target>    - Double-click (open files, edit cells, select words)
        right-click <target>     - Right-click (context menus)
        triple-click <target>    - Triple-click (select line/paragraph)
        click <X> in row with <Y> - Click element in a table row matching Y
        hover <target>           - Move mouse over element (tooltips, hover menus)
        type <text>              - Type into focused element
        type <text> in <target>  - Find a field, focus it, type
        fill Name=x, Email=y    - Fill multiple fields at once
        press <keys>             - Keyboard shortcut (e.g. "press cmd+s")
        open <app>               - Launch an application
        switch to <app>          - Bring an app to front
        scroll down/up           - Scroll the page
        scroll down in <element> - Scroll inside a specific element
        scroll until <target>    - Keep scrolling until element appears
        drag <src> to <dest>     - Drag element to another (or coordinates)
        focus <target>           - Find & focus an element
        close                    - Close the focused window
        copy / paste / undo      - Common shortcuts
        get clipboard            - Read clipboard contents
        get url / get tabs       - Safari info
        read table               - Extract structured table data
        read list                - Extract structured list data
        minimize                 - Minimize the focused window
        minimize <app>           - Minimize a specific app's window
        restore <app>            - Unminimize / restore a window
        resize to WxH            - Resize window to specific dimensions
        resize <app> to WxH      - Resize a specific app's window
        resize to N%             - Resize window to percentage of screen
        tile <app> and <app>     - Tile two windows side by side
        move window left/right   - Position window (halves, quarters, thirds, coordinates)
        move window top-left     - Position in a quarter of the screen
        move window top/bottom   - Position in top or bottom half
        move window left-third   - Position in a screen third
        move <app> to X,Y        - Move window to specific coordinates
        maximize                 - Maximize focused window (fills screen)
        fullscreen               - Toggle true macOS fullscreen (green button)
        exit fullscreen          - Exit fullscreen mode
        where is <app>?          - Get window position, size, and state
        list windows             - List all visible windows with positions
        navigate <url>           - Open URL in Chrome (CDP)
        js <expression>          - Run JavaScript in Chrome (CDP)
        switch tab <n>           - Switch Chrome tab by number or title (CDP)
        new tab [url]            - Open new Chrome tab (CDP)
        close tab [n]            - Close Chrome tab (CDP)
        observe start             - Start watching for UI changes (buffered in see())
        observe stop              - Stop watching
        observe status            - Show what's being observed
        observe clear             - Discard buffered events
        notify <message>         - macOS notification
        say <text>               - Speak aloud

    Verbs are flexible — synonyms like "tap", "hit", "enter", "visit" work too.
    Chain multiple actions with semicolons — fails fast on first error.

    Mutating actions automatically verify themselves — the response
    includes what changed on screen after the action.

    Use `see` first to know what elements are available.
    Use `see(menus=true)` to discover what menu commands are available.
    When Chrome is focused, `see` includes web page content via CDP.
    """
    from nexus.act.resolve import do as _do
    from nexus.state import read_state, write_state, read_and_clear_hint, start_action, end_action, emit
    import time

    try:
        from nexus.mind.session import tick
        tick()
    except Exception:
        pass

    _do_start_ts = time.time()

    # --- Panel integration: check pause + read hints ---
    state = read_state()
    if state.get("paused"):
        return "Paused by user via Nexus panel. Waiting to be resumed."

    hint = read_and_clear_hint()

    # Normalize: FastMCP may pass "" instead of None for unspecified params
    app = app.strip() if isinstance(app, str) and app.strip() else None

    # Resolve app name to PID
    pid = None
    if app:
        from nexus.sense.fusion import _resolve_pid
        pid = _resolve_pid(app)

    # Detect which app should have focus after this action
    focus_app = _detect_focus_target(action, app)

    # Broadcast current action to panel
    start_action("do", action, app=app or "")

    # Determine if this action mutates the screen (skip verification for getters)
    lower = action.strip().lower()
    is_getter = any(lower.startswith(g) for g in (
        "get ", "read ", "clipboard", "url", "tabs", "source", "selection",
        "hover", "table", "list", "observe", "where ", "window info", "console",
    ))

    # Snapshot before (skip for read-only actions)
    before = None
    if not is_getter:
        emit("Snapshotting before action...")
        from nexus.sense.fusion import snap
        try:
            before = snap(pid=pid)
        except Exception:
            before = None

    # Hook: before_do — circuit breaker (stops on consecutive failures)
    from nexus.hooks import fire as _fire_hook
    before_do_ctx = _fire_hook("before_do", {
        "action": action, "pid": pid, "app_param": app,
    })
    if before_do_ctx.get("stop"):
        end_action("failed")
        return before_do_ctx.get("error", "Action blocked by before_do hook.")

    result = _do(action, pid=pid)

    # Auto-retry on wrong app focused (Phase 7d)
    if not result.get("ok") and app and pid:
        result = _maybe_retry_wrong_app(result, action, app, pid, _do, emit)

    # Snapshot after + verify (brief pause lets UI update)
    changes = ""
    after = None
    if before is not None and result.get("ok"):
        emit("Verifying changes...")
        time.sleep(0.15)
        from nexus.sense.fusion import snap, verify
        try:
            after = snap(pid=pid)
            changes = verify(before, after)
        except Exception:
            changes = ""

    # Hook: after_do — learning, journal, workflow recording, graph recording
    from nexus.hooks import fire
    verb, target = _parse_verb_target(action)
    app_name = _app_name_for_learning(app, pid)
    before_hash = before.get("layout_hash") if before else None
    after_hash = after.get("layout_hash") if after else None
    fire("after_do", {
        "action": action, "pid": pid, "result": result,
        "app_name": app_name, "elapsed": round(time.time() - _do_start_ts, 2),
        "changes": changes, "verb": verb, "target": target,
        "app_param": app,
        "before_hash": before_hash, "after_hash": after_hash,
    })

    # Format as readable text
    parts = []

    # Prepend user hint if present
    if hint:
        parts.append(f"User note: {hint}")

    if result.get("ok"):
        end_action("done")
        parts.append(f"Done: {action}")
        if result.get("element"):
            el = result["element"]
            parts.append(f'  Target: [{el.get("role", "?")}] "{el.get("label", "")}"')
        if result.get("at"):
            parts.append(f"  At: {result['at']}")
        if result.get("item"):
            parts.append(f'  Menu: {result["item"]}')
        # Return data from getters (clipboard, url, tabs, etc.)
        if result.get("text"):
            parts.append(result["text"])
        if result.get("url"):
            parts.append(result["url"])
        if result.get("tabs"):
            parts.append("Tabs: " + ", ".join(result["tabs"]))
        if result.get("paths"):
            parts.append("Selected: " + ", ".join(result["paths"]))
        # Action verification — what changed?
        if changes:
            parts.append("")
            parts.append(changes)
        # Post-action state — saves the agent a see() call
        if not is_getter and before is not None:
            try:
                from nexus.sense.fusion import compact_state
                state_text = compact_state(pid=pid)
                if state_text:
                    parts.append("")
                    parts.append("--- State ---")
                    parts.append(state_text)
            except Exception:
                pass  # State must never break the action response
        # Session journal — recent actions for proprioception
        if not is_getter:
            try:
                from nexus.mind.session import journal_recent
                recent = journal_recent(n=3)
                if recent:
                    parts.append("")
                    parts.append("--- Recent ---")
                    parts.append(recent)
            except Exception:
                pass
        # Restore focus to target app (VS Code steals it back on MCP response)
        if focus_app:
            _schedule_focus_restore(focus_app)
        return "\n".join(parts)
    else:
        error_msg = result.get("error", "unknown")
        end_action("failed", error=error_msg)
        parts.append(f"Failed: {action}")
        parts.append(f"  Error: {error_msg}")
        if result.get("suggestions"):
            parts.append(f"  Did you mean: {', '.join(result['suggestions'])}")
        if result.get("found_roles"):
            parts.append(f"  On screen: {', '.join(result['found_roles'])}")
        if result.get("available"):
            parts.append(f"  Available: {', '.join(result['available'][:10])}")

        # Hook: on_error — suggest CLI alternatives from skills
        error_ctx = _fire_hook("on_error", {
            "action": action, "pid": pid, "app_name": app_name,
            "error": error_msg, "result": result, "app_param": app,
        })
        if error_ctx.get("skill_hint"):
            parts.append(f"  Skill: {error_ctx['skill_hint']}")
        for hint in error_ctx.get("extra_hints", []):
            parts.append(f"  Hint: {hint}")

        # Rich context snapshot on failure
        try:
            from nexus.sense.access import describe_app, focused_element, window_title, frontmost_app
            target_pid = pid
            if not target_pid:
                info = frontmost_app()
                if info:
                    target_pid = info["pid"]
            if target_pid:
                parts.append("")
                wt = window_title(target_pid)
                if wt:
                    parts.append(f"  Window: \"{wt}\"")
                focused = focused_element(target_pid)
                if focused:
                    parts.append(f"  Focused: [{focused.get('role', '?')}] \"{focused.get('label', '')}\"")
                elements = describe_app(target_pid)
                if elements:
                    summary = []
                    for el in elements:
                        label = el.get("label", "")
                        if label:
                            summary.append(f"[{el.get('role', '?')}] \"{label}\"")
                        if len(summary) >= 8:
                            break
                    if summary:
                        parts.append(f"  Visible ({len(elements)} elements): {', '.join(summary)}")
                parts.append("  Tip: Use see() for full element tree, or see(query=\"...\") to search.")
        except Exception:
            pass  # Context must never break the error response

        # Session journal — recent actions for proprioception
        try:
            from nexus.mind.session import journal_recent
            recent = journal_recent(n=3)
            if recent:
                parts.append("")
                parts.append("--- Recent ---")
                parts.append(recent)
        except Exception:
            pass

        return "\n".join(parts)


@mcp.tool(
    annotations={
        "title": "Memory",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
def memory(
    op: str,
    key: str | None = None,
    value: str | None = None,
) -> str:
    """Persistent memory across sessions.

    Remember things you learn — user preferences, file paths,
    app configurations, workflow patterns.

    Operations:
        set   - Store a value:  memory(op="set", key="editor", value="VS Code")
        get   - Retrieve:       memory(op="get", key="editor")
        list  - See all keys:   memory(op="list")
        delete - Remove a key:  memory(op="delete", key="editor")
        clear - Delete all:     memory(op="clear")
        stats - Show learning stats (label mappings, action history size)
    """
    try:
        from nexus.mind.session import tick
        tick()
    except Exception:
        pass

    # Learning stats — separate from user memory
    if op.lower().strip() == "stats":
        try:
            from nexus.mind.learn import stats as learn_stats
            s = learn_stats()
            parts = [
                f"Label mappings: {s['label_mappings']} app-specific, {s['global_mappings']} global",
                f"Actions recorded: {s['actions_recorded']}",
                f"Apps tracked: {s['apps_tracked']}",
            ]
            return "\n".join(parts)
        except Exception:
            return "Learning system not initialized."

    from nexus.mind.store import memory as _memory

    result = _memory(op=op, key=key, value=value)

    if result.get("ok"):
        if op == "get":
            return f'{result["key"]} = {result["value"]}'
        if op == "list":
            if result["count"] == 0:
                return "Memory is empty."
            return f'Keys ({result["count"]}): {", ".join(result["keys"])}'
        if op == "set":
            return f'Remembered: {key} = {value}'
        if op == "delete":
            return f"Deleted: {key}"
        if op == "clear":
            return "Memory cleared."
        return "OK"
    else:
        return f'Error: {result.get("error", "unknown")}'


def _app_name_for_learning(app_param, pid):
    """Get app name for learning records."""
    if app_param:
        return app_param
    from nexus.sense.access import frontmost_app
    info = frontmost_app()
    return info["name"] if info else ""


def _parse_verb_target(action):
    """Extract verb and target from an action string."""
    parts = action.strip().split(None, 1)
    verb = parts[0].lower() if parts else ""
    target = parts[1] if len(parts) > 1 else ""
    # Normalize common verb synonyms
    from nexus.act.resolve import VERB_SYNONYMS
    verb = VERB_SYNONYMS.get(verb, verb)
    return verb, target


def _maybe_retry_wrong_app(result, action, app, pid, _do, emit):
    """Retry once if action failed because the wrong app has focus.

    Only retries when app= param was explicitly set and the frontmost app
    doesn't match. Max 1 retry. Returns original result if retry not needed.
    """
    try:
        from nexus.sense.access import frontmost_app, invalidate_cache
        current = frontmost_app()
        if not current or current["pid"] == pid:
            return result  # Correct app is focused, don't retry
        emit(f"Wrong app focused ({current['name']}), re-activating {app}...")
        import subprocess
        subprocess.run(
            ["osascript", "-e", f'tell application "{app}" to activate'],
            capture_output=True, timeout=5,
        )
        import time
        time.sleep(0.3)
        invalidate_cache()
        retry_result = _do(action, pid=pid)
        if retry_result.get("ok"):
            retry_result["retried"] = True
            retry_result["retry_reason"] = f"Re-activated {app} (was {current['name']})"
        return retry_result
    except Exception:
        return result  # Retry is best-effort


def _detect_focus_target(action, app_param):
    """Detect which app should have focus after this action.

    Returns app name string if focus should be restored, None otherwise.
    Only triggers for actions that explicitly move focus to another app.
    """
    # For action chains, check the last action (it determines final focus)
    if ";" in action:
        parts = action.split(";")
        last_action = parts[-1].strip()
        # But also check earlier actions for app switches
        for part in reversed(parts):
            result = _detect_focus_target(part.strip(), app_param)
            if result:
                return result
        return None

    lower = action.strip().lower()

    # Getter actions never need focus restore
    if any(lower.startswith(g) for g in (
        "get ", "read ", "clipboard", "url", "tabs", "source",
        "hover", "observe",
    )):
        return None

    # "switch to Safari", "open Safari" — extract target app name
    for prefix in ("switch to ", "activate ", "bring "):
        if lower.startswith(prefix):
            target = action.strip()[len(prefix):]
            if target and not target.lower().startswith("tab"):
                return target

    if lower.startswith("open "):
        target = action.strip()[5:]
        # Don't restore for "open file.txt" — only for app names
        if target and "." not in target and "/" not in target:
            return target

    # app= parameter targets a specific app — restore focus there
    # (only for mutating actions like click, type, press)
    if app_param and any(lower.startswith(v) for v in (
        "click", "type", "press", "fill", "scroll", "drag",
        "focus", "close", "select", "tap", "hit",
    )):
        return app_param

    return None


def _schedule_focus_restore(app_name, delay=0.4):
    """Restore focus to an app after VS Code steals it back.

    Spawns a background thread that waits for VS Code to reclaim focus,
    then re-activates the target app via AppleScript.
    """
    import threading
    import subprocess

    def _restore():
        import time
        time.sleep(delay)
        try:
            subprocess.run(
                ["osascript", "-e", f'tell application "{app_name}" to activate'],
                capture_output=True, timeout=5,
            )
        except Exception:
            pass

    threading.Thread(target=_restore, daemon=True).start()


# ── Skill resources ──────────────────────────────────────────────


@mcp.resource("nexus://skills")
def skills_catalog() -> str:
    """List all available skills — CLI shortcuts for common tasks.

    Each skill teaches you which CLI tool to use instead of GUI automation.
    Read a specific skill with nexus://skills/{id} for full documentation.
    """
    from nexus.mind.skills import list_skills

    skills = list_skills()
    if not skills:
        return "No skills installed. Add .md files to ~/.nexus/skills/"

    lines = ["Available skills:\n"]
    for s in skills:
        status = "ready" if s["available"] else f"needs: {', '.join(s['requires'])}"
        lines.append(f"  {s['id']} — {s['description']} [{status}]")
    lines.append(f"\nTotal: {len(skills)} skills. Read one: nexus://skills/{{id}}")
    return "\n".join(lines)


@mcp.resource("nexus://skills/{skill_id}")
def skill_detail(skill_id: str) -> str:
    """Read a specific skill's full documentation and CLI commands."""
    from nexus.mind.skills import read_skill

    content = read_skill(skill_id)
    if content is None:
        from nexus.mind.skills import list_skills
        available = [s["id"] for s in list_skills()]
        return f'Skill "{skill_id}" not found. Available: {", ".join(available)}'
    return content


@mcp.resource("nexus://workflows")
def workflows_catalog() -> str:
    """List all recorded workflows."""
    from nexus.mind.workflows import list_workflows

    wfs = list_workflows()
    if not wfs:
        return "No workflows recorded. Use do('record start <name>') to start recording."
    lines = ["Recorded workflows:\n"]
    for wf in wfs:
        lines.append(f"  {wf['id']} — {wf['name']} ({wf['step_count']} steps)")
    return "\n".join(lines)


@mcp.resource("nexus://workflows/{workflow_id}")
def workflow_detail(workflow_id: str) -> str:
    """Read a workflow's steps."""
    from nexus.mind.workflows import get_workflow

    wf = get_workflow(workflow_id)
    if not wf:
        return f'Workflow "{workflow_id}" not found.'
    lines = [f"Workflow: {wf['name']}"]
    if wf.get("app"):
        lines.append(f"App: {wf['app']}")
    lines.append("Steps:")
    for step in wf.get("steps", []):
        lines.append(f"  {step['step_num']}. {step['action']}")
    return "\n".join(lines)


def main():
    """Start the MCP server (stdio transport)."""
    mcp.run(transport="stdio")
