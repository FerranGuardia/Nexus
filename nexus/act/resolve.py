"""Intent resolution — the `do` tool.

Parses natural-language-ish intents and routes to the best action.
The AI calls do("click Save") and Nexus figures out the rest.

Supported intents:
    click <target>              → find & click element
    click <menu > path>         → click menu item (e.g. "click File > Save")
    double-click <target>       → find & double-click element
    right-click <target>        → find & right-click element
    type <text>                 → type into focused element
    type <text> in <target>     → find target, focus, type
    press <keys>                → keyboard shortcut (e.g. "press cmd+s")
    open <app>                  → launch application
    switch to <app>             → activate app/window
    scroll <direction>          → scroll up/down/left/right
    focus <target>              → find & focus element
    close                       → close focused window
    select all / copy / paste / undo / redo
    get clipboard               → read clipboard contents
    get url                     → get Safari's current URL
    get tabs                    → list Safari's tabs
    tile <app1> and <app2>      → tile two apps side by side
    maximize                    → maximize focused window
    move window left/right/full → position window
    menu <path>                 → click a menu item by path
    notify <message>            → show macOS notification
    say <text>                  → speak text aloud
"""

import re
from nexus.act import native, input as raw_input


# Key name mappings for "press" intent
KEY_ALIASES = {
    "cmd": "command", "command": "command",
    "ctrl": "control", "control": "control",
    "alt": "option", "opt": "option", "option": "option",
    "shift": "shift",
    "enter": "return", "return": "return",
    "esc": "escape", "escape": "escape",
    "tab": "tab",
    "space": "space",
    "delete": "delete", "backspace": "delete",
    "up": "up", "down": "down", "left": "left", "right": "right",
    "home": "home", "end": "end",
    "pageup": "pageup", "pagedown": "pagedown",
    "f1": "f1", "f2": "f2", "f3": "f3", "f4": "f4",
    "f5": "f5", "f6": "f6", "f7": "f7", "f8": "f8",
    "f9": "f9", "f10": "f10", "f11": "f11", "f12": "f12",
}


def do(action):
    """Execute a natural-language intent.

    Args:
        action: Intent string like "click Save", "type hello in search".

    Returns:
        dict with action result.
    """
    action = action.strip()
    if not action:
        return {"ok": False, "error": "Empty action"}

    # Normalize
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

    if lower in ("close", "close window"):
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

    if lower in ("maximize", "maximize window", "fullscreen"):
        return native.maximize_window()

    # --- Verb-based intents ---
    verb, _, rest = action.partition(" ")
    verb = verb.lower()
    rest = rest.strip()

    # Menu paths: "click File > Save" or "menu File > Save"
    if verb in ("click", "menu") and ">" in rest:
        return native.click_menu(rest)

    if verb == "click":
        return _handle_click(rest)

    if verb in ("double-click", "doubleclick", "dblclick"):
        return _handle_click(rest, double=True)

    if verb in ("right-click", "rightclick", "rclick"):
        return _handle_click(rest, right=True)

    if verb == "type":
        return _handle_type(rest)

    if verb == "press":
        return _handle_press(rest)

    if verb == "open":
        return native.launch_app(rest)

    if verb in ("switch", "activate"):
        target = rest
        if target.lower().startswith("to "):
            target = target[3:]
        return native.activate_window(app_name=target.strip())

    if verb == "scroll":
        return _handle_scroll(rest)

    if verb == "focus":
        return native.focus_element(rest)

    if verb == "drag":
        return _handle_drag(rest)

    if verb == "tile":
        return _handle_tile(rest)

    if verb in ("move", "position"):
        return _handle_move(rest)

    if verb == "menu":
        return native.click_menu(rest)

    if verb == "notify":
        return native.notify("Nexus", rest)

    if verb == "say":
        return native.say(rest)

    if verb in ("set", "write") and rest.lower().startswith("clipboard "):
        text = rest[10:]  # after "clipboard "
        return native.clipboard_write(_strip_quotes(text))

    # Unknown verb — check for menu path, then try as a click target
    if ">" in action:
        return native.click_menu(action)
    return _handle_click(action)


def _handle_click(target, double=False, right=False):
    """Handle click intents."""
    if not target:
        # Click at current mouse position
        pos = raw_input.mouse_position()
        if right:
            return raw_input.right_click(pos["x"], pos["y"])
        if double:
            return raw_input.double_click(pos["x"], pos["y"])
        return raw_input.click(pos["x"], pos["y"])

    # Check for coordinate click: "click 340,220" or "click at 340 220"
    coord_match = re.match(r"(?:at\s+)?(\d+)[,\s]+(\d+)", target)
    if coord_match:
        x, y = int(coord_match.group(1)), int(coord_match.group(2))
        if right:
            return raw_input.right_click(x, y)
        if double:
            return raw_input.double_click(x, y)
        return raw_input.click(x, y)

    # Parse optional role filter: "click button Save" or "click Save button"
    role = None
    parts = target.split()
    role_words = {"button", "link", "tab", "menu", "field", "checkbox", "radio", "text"}
    if len(parts) >= 2:
        if parts[0].lower() in role_words:
            role = parts[0]
            target = " ".join(parts[1:])
        elif parts[-1].lower() in role_words:
            role = parts[-1]
            target = " ".join(parts[:-1])

    result = native.click_element(target, role=role)

    # If native click worked but we need double/right click, use coordinates
    if result.get("ok") and (double or right):
        at = result.get("at")
        if at:
            if double:
                raw_input.double_click(at[0], at[1])
            elif right:
                raw_input.right_click(at[0], at[1])

    return result


def _handle_type(rest):
    """Handle type intents: 'type hello' or 'type hello in search'."""
    if not rest:
        return {"ok": False, "error": "Nothing to type"}

    # Check for "type <text> in <target>" pattern
    in_match = re.match(r"(.+?)\s+in\s+(.+)$", rest, re.IGNORECASE)
    if in_match:
        text = in_match.group(1).strip()
        target = in_match.group(2).strip()

        # Strip quotes from text if present
        text = _strip_quotes(text)

        # Focus the target first, then type
        return native.set_value(target, text)

    # Simple type: "type hello world"
    text = _strip_quotes(rest)
    raw_input.type_text(text)
    return {"ok": True, "action": "type", "text": text}


def _handle_press(keys_str):
    """Handle press intents: 'press cmd+s', 'press enter'."""
    if not keys_str:
        return {"ok": False, "error": "No key specified"}

    # Split on + or space
    parts = re.split(r"[+\s]+", keys_str.strip())
    resolved = []

    for part in parts:
        key = KEY_ALIASES.get(part.lower(), part.lower())
        resolved.append(key)

    if len(resolved) == 1:
        raw_input.press(resolved[0])
    else:
        raw_input.hotkey(*resolved)

    return {"ok": True, "action": "press", "keys": resolved}


def _handle_scroll(direction):
    """Handle scroll intents."""
    direction = direction.lower().strip()

    amount = 3  # Default scroll amount
    # Check for "scroll down 5" pattern
    parts = direction.split()
    if len(parts) >= 2 and parts[-1].isdigit():
        amount = int(parts[-1])
        direction = parts[0]

    if direction in ("down", "d"):
        return raw_input.scroll(-amount)
    elif direction in ("up", "u"):
        return raw_input.scroll(amount)
    elif direction in ("left", "l"):
        # macOS horizontal scroll via pyautogui isn't great
        raw_input.hotkey("shift", "scroll")  # Might not work
        return {"ok": True, "action": "scroll_left", "note": "horizontal scroll may not work everywhere"}
    elif direction in ("right", "r"):
        return {"ok": True, "action": "scroll_right", "note": "horizontal scroll may not work everywhere"}
    else:
        return raw_input.scroll(-amount)  # Default: down


def _handle_drag(rest):
    """Handle drag intents: 'drag 100,200 to 300,400'."""
    match = re.match(r"(\d+)[,\s]+(\d+)\s+to\s+(\d+)[,\s]+(\d+)", rest)
    if match:
        x1, y1, x2, y2 = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
        return raw_input.drag(x1, y1, x2, y2)
    return {"ok": False, "error": "Drag format: 'drag x1,y1 to x2,y2'"}


def _handle_tile(rest):
    """Handle: 'tile Safari and Terminal', 'tile Code Terminal'."""
    # Try "X and Y" pattern
    match = re.match(r"(.+?)\s+and\s+(.+)", rest, re.IGNORECASE)
    if match:
        return native.tile_windows(match.group(1).strip(), match.group(2).strip())

    # Try two space-separated words
    parts = rest.split()
    if len(parts) == 2:
        return native.tile_windows(parts[0], parts[1])

    return {"ok": False, "error": 'Tile format: "tile Safari and Terminal"'}


def _handle_move(rest):
    """Handle: 'move window left', 'move window right', 'move Safari left'."""
    lower = rest.lower()
    from nexus.act.input import screen_size
    sz = screen_size()
    half_w = sz["width"] // 2
    h = sz["height"] - 25

    # Parse optional app name: "move Safari left" or "move window left"
    app_name = None
    direction = lower
    words = lower.split()
    if len(words) >= 2:
        direction = words[-1]
        candidate = " ".join(words[:-1])
        if candidate != "window":
            app_name = candidate

    if direction in ("left", "l"):
        return native.move_window(app_name, x=0, y=25, w=half_w, h=h)
    elif direction in ("right", "r"):
        return native.move_window(app_name, x=half_w, y=25, w=half_w, h=h)
    elif direction in ("center", "centre", "c"):
        qw = sz["width"] // 4
        return native.move_window(app_name, x=qw, y=25, w=half_w, h=h)
    elif direction in ("full", "max", "maximize"):
        return native.maximize_window(app_name)
    else:
        return {"ok": False, "error": f'Unknown direction: {direction}. Use: left, right, center, full'}


def _strip_quotes(text):
    """Strip surrounding quotes if present."""
    if len(text) >= 2:
        if (text[0] == '"' and text[-1] == '"') or (text[0] == "'" and text[-1] == "'"):
            return text[1:-1]
    return text
