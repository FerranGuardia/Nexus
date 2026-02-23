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
        "Use `memory` to remember things across sessions."
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

    Call this first to understand what the user sees.
    For apps with many elements, use query= to search instead of browsing the full tree.
    When Chrome is focused, `see` includes web page content via CDP.
    """
    from nexus.sense.fusion import see as _see

    result = _see(app=app, query=query, screenshot=screenshot, menus=menus, diff=diff, content=content)

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
        type <text>              - Type into focused element
        type <text> in <target>  - Find a field, focus it, type
        fill Name=x, Email=y    - Fill multiple fields at once
        press <keys>             - Keyboard shortcut (e.g. "press cmd+s")
        open <app>               - Launch an application
        switch to <app>          - Bring an app to front
        scroll down/up           - Scroll the page
        focus <target>           - Find & focus an element
        close                    - Close the focused window
        copy / paste / undo      - Common shortcuts
        get clipboard            - Read clipboard contents
        get url / get tabs       - Safari info
        tile <app> and <app>     - Tile two windows side by side
        move window left/right   - Position window on screen half
        maximize                 - Maximize focused window
        navigate <url>           - Open URL in Chrome (CDP)
        js <expression>          - Run JavaScript in Chrome (CDP)
        switch tab <n>           - Switch Chrome tab by number or title (CDP)
        new tab [url]            - Open new Chrome tab (CDP)
        close tab [n]            - Close Chrome tab (CDP)
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

    # Determine if this action mutates the screen (skip verification for getters)
    lower = action.strip().lower()
    is_getter = any(lower.startswith(g) for g in (
        "get ", "read ", "clipboard", "url", "tabs", "source", "selection",
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
    """
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


def main():
    """Start the MCP server (stdio transport)."""
    mcp.run(transport="stdio")
