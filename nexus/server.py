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
        "Nexus is the physical layer — only use it for what you literally cannot do without it."
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

    # Resolve app name to PID at server level (avoids MCP parameter passing issues)
    pid = _resolve_pid(app) if app else None
    result = _see(app=pid, query=query, screenshot=screenshot, menus=menus, diff=diff, content=content, observe=observe)

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
    import time

    # Resolve app name to PID
    pid = None
    if app:
        from nexus.sense.fusion import _resolve_pid
        pid = _resolve_pid(app)

    # Detect which app should have focus after this action
    focus_app = _detect_focus_target(action, app)

    # Determine if this action mutates the screen (skip verification for getters)
    lower = action.strip().lower()
    is_getter = any(lower.startswith(g) for g in (
        "get ", "read ", "clipboard", "url", "tabs", "source", "selection",
        "hover", "table", "list", "observe", "where ", "window info",
    ))

    # Snapshot before (skip for read-only actions)
    before = None
    if not is_getter:
        from nexus.sense.fusion import snap
        try:
            before = snap(pid=pid)
        except Exception:
            before = None

    result = _do(action, pid=pid)

    # Record action outcome for learning (label correlation + history)
    try:
        from nexus.mind.learn import record_action, record_failure, correlate_success
        app_name = _app_name_for_learning(app, pid)
        verb, target = _parse_verb_target(action)
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
            record_action(app_name=app_name, intent=action, ok=False,
                          verb=verb, target=target)
    except Exception:
        pass  # Learning must never break the action pipeline

    # Snapshot after + verify (brief pause lets UI update)
    changes = ""
    if before is not None and result.get("ok"):
        time.sleep(0.15)
        from nexus.sense.fusion import snap, verify
        try:
            after = snap(pid=pid)
            changes = verify(before, after)
        except Exception:
            changes = ""

    # Format as readable text
    if result.get("ok"):
        parts = [f"Done: {action}"]
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
        # Restore focus to target app (VS Code steals it back on MCP response)
        if focus_app:
            _schedule_focus_restore(focus_app)
        return "\n".join(parts)
    else:
        parts = [f"Failed: {action}", f'  Error: {result.get("error", "unknown")}']
        if result.get("suggestions"):
            parts.append(f"  Did you mean: {', '.join(result['suggestions'])}")
        if result.get("found_roles"):
            parts.append(f"  On screen: {', '.join(result['found_roles'])}")
        if result.get("available"):
            parts.append(f"  Available: {', '.join(result['available'][:10])}")
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


def main():
    """Start the MCP server (stdio transport)."""
    mcp.run(transport="stdio")
