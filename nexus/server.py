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

    Call this first to understand what the user sees.
    """
    from nexus.sense.fusion import see as _see

    result = _see(app=app, query=query, screenshot=screenshot, menus=menus, diff=diff)

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
def do(action: str) -> str:
    """Execute an action on the computer.

    Verb-first intent format. Nexus finds the best way to execute it
    (accessibility actions, AppleScript, or keyboard/mouse).

    Supported intents:
        click <target>           - Find & click element by name
        click <File > Save>      - Click a menu item by path
        type <text>              - Type into focused element
        type <text> in <target>  - Find a field, focus it, type
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
        notify <message>         - macOS notification
        say <text>               - Speak aloud

    Use `see` first to know what elements are available.
    Use `see(menus=true)` to discover what menu commands are available.
    """
    from nexus.act.resolve import do as _do

    result = _do(action)

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
        return "\n".join(parts)
    else:
        parts = [f"Failed: {action}", f'  Error: {result.get("error", "unknown")}']
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
