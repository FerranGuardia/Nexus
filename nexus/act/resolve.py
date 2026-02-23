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


# ---------------------------------------------------------------------------
# Verb synonym expansion — normalize natural phrasing before dispatch
# ---------------------------------------------------------------------------

VERB_SYNONYMS = {
    # click synonyms
    "tap": "click", "hit": "click", "select": "click", "choose": "click",
    "pick": "click", "push": "click", "touch": "click",
    # type synonyms (not "write" — conflicts with "write clipboard")
    "enter": "type", "input": "type",
    # open synonyms (not "run" — conflicts with "run js")
    "launch": "open", "start": "open",
    # close synonyms (quit/exit handled directly in shortcut intents)

    # scroll synonyms
    "swipe": "scroll",
    # navigate synonyms
    "browse": "navigate", "visit": "navigate", "load": "navigate",
    # focus synonyms
    "find": "focus", "locate": "focus",
    # switch synonyms
    "bring": "switch",
}

# Multi-word verb phrases that need special handling
PHRASE_SYNONYMS = {
    "press on": "click",
    "click on": "click",
    "tap on": "click",
    "go to": "navigate",
    "switch to": "switch to",
    "type in": "type",
    "move to": "navigate",
    "look at": "focus",
}


def _normalize_action(action):
    """Expand verb synonyms so the dispatcher sees canonical verbs.

    Handles both single-word synonyms ("tap Save" → "click Save")
    and multi-word phrases ("press on Save" → "click Save").
    """
    stripped = action.strip()
    lower = stripped.lower()

    # Try multi-word phrase synonyms first (longest match wins)
    for phrase, canonical in PHRASE_SYNONYMS.items():
        if lower.startswith(phrase + " "):
            rest = stripped[len(phrase):].strip()
            return f"{canonical} {rest}"
        if lower == phrase:
            return canonical

    # Single-word verb synonym
    parts = stripped.split(None, 1)
    if parts:
        verb_lower = parts[0].lower()
        if verb_lower in VERB_SYNONYMS:
            canonical = VERB_SYNONYMS[verb_lower]
            rest = parts[1] if len(parts) > 1 else ""
            return f"{canonical} {rest}".strip()

    return stripped


# ---------------------------------------------------------------------------
# Ordinal parsing — "click the 2nd button", "the third link", etc.
# ---------------------------------------------------------------------------

ORDINAL_WORDS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
    "last": -1,
}

# Matches "1st", "2nd", "3rd", "4th", "11th", "22nd", etc.
ORDINAL_NUM_RE = re.compile(r"^(\d+)(?:st|nd|rd|th)$", re.IGNORECASE)


def _parse_ordinal(text):
    """Parse ordinal references from a click target.

    Returns (ordinal, role, remaining_label) or None if no ordinal found.
    ordinal is 1-based (or -1 for "last").

    Supported patterns:
        "the 2nd button"         → (2, "button", "")
        "3rd link"               → (3, "link", "")
        "the last checkbox"      → (-1, "checkbox", "")
        "first Save button"      → (1, "button", "Save")
        "button 3"               → (3, "button", "")
        "second link on the page"→ (2, "link", "")
    """
    words = text.split()
    if not words:
        return None

    # Strip leading "the"
    if words[0].lower() == "the":
        words = words[1:]
    if not words:
        return None

    role_words = {"button", "link", "tab", "menu", "field", "checkbox",
                  "radio", "text", "image", "slider", "switch", "toggle"}

    # Pattern 1: "<ordinal> [label...] <role>" — "2nd button", "third Save button"
    ordinal = _word_to_ordinal(words[0])
    if ordinal is not None and len(words) >= 2:
        # Find the role word (usually the last word)
        for i in range(len(words) - 1, 0, -1):
            if words[i].lower() in role_words:
                role = words[i].lower()
                label = " ".join(words[1:i]).strip()
                return (ordinal, role, label)

    # Pattern 2: "<role> <number>" — "button 3", "link 2"
    if len(words) >= 2 and words[0].lower() in role_words and words[-1].isdigit():
        role = words[0].lower()
        ordinal = int(words[-1])
        label = " ".join(words[1:-1]).strip()
        return (ordinal, role, label)

    return None


def _word_to_ordinal(word):
    """Convert a word to an ordinal number, or None."""
    lower = word.lower()
    if lower in ORDINAL_WORDS:
        return ORDINAL_WORDS[lower]
    m = ORDINAL_NUM_RE.match(lower)
    if m:
        return int(m.group(1))
    return None


# ---------------------------------------------------------------------------
# Spatial element resolution — "button near search", "field below Username"
# ---------------------------------------------------------------------------

_SPATIAL_ROLE_WORDS = {
    "button", "link", "tab", "menu", "field", "checkbox",
    "radio", "text", "image", "slider", "switch", "toggle",
    "icon", "label",
}

_SPATIAL_ROLE_MAP = {
    "button": "AXButton", "link": "AXLink", "tab": "AXTab",
    "menu": "AXMenuItem", "field": "AXTextField", "checkbox": "AXCheckBox",
    "radio": "AXRadioButton", "text": "AXStaticText", "image": "AXImage",
    "slider": "AXSlider", "switch": "AXSwitch", "toggle": "AXSwitch",
    "icon": "AXImage",
}

SPATIAL_RELATIONS = [
    (re.compile(r'^(.+?)\s+(?:below|under|beneath|underneath)\s+(.+)$', re.IGNORECASE), 'below'),
    (re.compile(r'^(.+?)\s+(?:above|over)\s+(.+)$', re.IGNORECASE), 'above'),
    (re.compile(r'^(.+?)\s+(?:left\s+of|to\s+the\s+left\s+of)\s+(.+)$', re.IGNORECASE), 'left'),
    (re.compile(r'^(.+?)\s+(?:right\s+of|to\s+the\s+right\s+of)\s+(.+)$', re.IGNORECASE), 'right'),
    (re.compile(r'^(.+?)\s+(?:near|beside|next\s+to|by|close\s+to)\s+(.+)$', re.IGNORECASE), 'near'),
]

REGION_PATTERNS = [
    (re.compile(r'^(.+?)\s+(?:in|at)\s+(?:the\s+)?(?:top[- ]?right|upper[- ]?right)', re.IGNORECASE), 'top-right'),
    (re.compile(r'^(.+?)\s+(?:in|at)\s+(?:the\s+)?(?:top[- ]?left|upper[- ]?left)', re.IGNORECASE), 'top-left'),
    (re.compile(r'^(.+?)\s+(?:in|at)\s+(?:the\s+)?(?:bottom[- ]?right|lower[- ]?right)', re.IGNORECASE), 'bottom-right'),
    (re.compile(r'^(.+?)\s+(?:in|at)\s+(?:the\s+)?(?:bottom[- ]?left|lower[- ]?left)', re.IGNORECASE), 'bottom-left'),
    (re.compile(r'^(.+?)\s+(?:in|at)\s+(?:the\s+)?(?:top|upper)(?:\s+(?:area|region|part|corner|half))?$', re.IGNORECASE), 'top'),
    (re.compile(r'^(.+?)\s+(?:in|at)\s+(?:the\s+)?(?:bottom|lower)(?:\s+(?:area|region|part|corner|half))?$', re.IGNORECASE), 'bottom'),
    (re.compile(r'^(.+?)\s+(?:in|at)\s+(?:the\s+)?(?:center|middle|centre)', re.IGNORECASE), 'center'),
]


def _parse_spatial(text):
    """Parse spatial references from a click target.

    Returns (search_term, relation, reference) or None.

    Patterns:
        "button near search"          → ("button", "near", "search")
        "field below Username"        → ("field", "below", "Username")
        "close button above toolbar"  → ("close button", "above", "toolbar")
        "button in top-right"         → ("button", "region", "top-right")
    """
    stripped = text.strip()
    if stripped.lower().startswith("the "):
        stripped = stripped[4:]

    # Try directional/proximity patterns
    for pattern, relation in SPATIAL_RELATIONS:
        m = pattern.match(stripped)
        if m:
            search = m.group(1).strip()
            reference = m.group(2).strip()
            if reference.lower().startswith("the "):
                reference = reference[4:]
            if search and reference:
                return (search, relation, reference)

    # Try region patterns
    for pattern, region in REGION_PATTERNS:
        m = pattern.match(stripped)
        if m:
            search = m.group(1).strip()
            if search:
                return (search, "region", region)

    return None


def _filter_by_search(elements, search):
    """Filter elements by a search term — can be a role name, a label, or both."""
    search_lower = search.lower().strip()
    words = search_lower.split()

    role_word = None
    label_filter = ""

    if search_lower in _SPATIAL_ROLE_WORDS:
        role_word = search_lower
    elif len(words) >= 2 and words[-1] in _SPATIAL_ROLE_WORDS:
        role_word = words[-1]
        label_filter = " ".join(words[:-1])
    elif len(words) >= 2 and words[0] in _SPATIAL_ROLE_WORDS:
        role_word = words[0]
        label_filter = " ".join(words[1:])

    if role_word:
        ax_role = _SPATIAL_ROLE_MAP.get(role_word)
        if ax_role:
            matches = [el for el in elements if el.get("_ax_role") == ax_role]
        else:
            matches = [el for el in elements if role_word in el.get("role", "").lower()]
        if label_filter:
            labeled = [el for el in matches if label_filter in el.get("label", "").lower()]
            if labeled:
                matches = labeled
        return matches

    # Search by label
    exact = [el for el in elements if search_lower == el.get("label", "").lower()]
    if exact:
        return exact
    return [el for el in elements if search_lower in el.get("label", "").lower()]


def _click_spatial(spatial_info, double=False, right=False, pid=None):
    """Click an element using spatial relationship to a reference element."""
    from nexus.sense.access import describe_app, find_elements

    search, relation, reference = spatial_info

    if relation == "region":
        return _click_in_region(search, reference, double=double, right=right, pid=pid)

    ref_matches = find_elements(reference, pid)
    if not ref_matches:
        return {"ok": False, "error": f'Reference element "{reference}" not found'}

    ref_el = ref_matches[0]
    ref_pos = ref_el.get("pos")
    ref_size = ref_el.get("size")
    if not ref_pos:
        return {"ok": False, "error": f'Reference "{reference}" has no position'}

    ref_cx = ref_pos[0] + (ref_size[0] // 2 if ref_size else 0)
    ref_cy = ref_pos[1] + (ref_size[1] // 2 if ref_size else 0)

    all_elements = describe_app(pid)
    candidates = _filter_by_search(all_elements, search)

    # Exclude the reference element itself
    candidates = [
        el for el in candidates
        if el.get("pos") != ref_el.get("pos") or el.get("label") != ref_el.get("label")
    ]

    scored = []
    for el in candidates:
        pos = el.get("pos")
        if not pos:
            continue
        size = el.get("size")
        el_cx = pos[0] + (size[0] // 2 if size else 0)
        el_cy = pos[1] + (size[1] // 2 if size else 0)

        dx = el_cx - ref_cx
        dy = el_cy - ref_cy
        dist = (dx * dx + dy * dy) ** 0.5

        if relation == 'near':
            scored.append((dist, el))
        elif relation == 'below' and dy > 0:
            scored.append((dist + abs(dx) * 0.5, el))
        elif relation == 'above' and dy < 0:
            scored.append((dist + abs(dx) * 0.5, el))
        elif relation == 'left' and dx < 0:
            scored.append((dist + abs(dy) * 0.5, el))
        elif relation == 'right' and dx > 0:
            scored.append((dist + abs(dy) * 0.5, el))

    if not scored:
        dir_names = {
            "near": "near", "below": "below", "above": "above",
            "left": "left of", "right": "right of",
        }
        return {
            "ok": False,
            "error": f'No "{search}" found {dir_names.get(relation, relation)} "{reference}"',
            "reference_at": [ref_cx, ref_cy],
        }

    scored.sort(key=lambda x: x[0])
    target = scored[0][1]
    return _click_resolved(target, double=double, right=right)


def _click_in_region(search, region, double=False, right=False, pid=None):
    """Click an element in a specific screen region."""
    from nexus.sense.access import describe_app
    from nexus.act.input import screen_size

    sz = screen_size()
    w, h = sz["width"], sz["height"]

    regions = {
        'top-left': (0, 0, w // 2, h // 2),
        'top-right': (w // 2, 0, w, h // 2),
        'bottom-left': (0, h // 2, w // 2, h),
        'bottom-right': (w // 2, h // 2, w, h),
        'top': (0, 0, w, h // 3),
        'bottom': (0, 2 * h // 3, w, h),
        'center': (w // 4, h // 4, 3 * w // 4, 3 * h // 4),
    }

    bounds = regions.get(region)
    if not bounds:
        return {"ok": False, "error": f"Unknown region: {region}"}

    rx1, ry1, rx2, ry2 = bounds

    all_elements = describe_app(pid)
    candidates = _filter_by_search(all_elements, search)

    in_region = []
    for el in candidates:
        pos = el.get("pos")
        if not pos:
            continue
        size = el.get("size")
        cx = pos[0] + (size[0] // 2 if size else 0)
        cy = pos[1] + (size[1] // 2 if size else 0)
        if rx1 <= cx <= rx2 and ry1 <= cy <= ry2:
            in_region.append(el)

    if not in_region:
        return {
            "ok": False,
            "error": f'No "{search}" found in {region} region',
            "region_bounds": [rx1, ry1, rx2, ry2],
        }

    return _click_resolved(in_region[0], double=double, right=right)


def _click_resolved(target, double=False, right=False):
    """Click a resolved element dict. Used by spatial and region resolution."""
    from nexus.sense.access import ax_actions, ax_perform

    ref = target.get("_ref")
    pos = target.get("pos")
    size = target.get("size")

    clicked = False
    at = None

    if ref and not (double or right):
        actions = ax_actions(ref)
        if "AXPress" in actions:
            clicked = ax_perform(ref, "AXPress")
        elif "AXConfirm" in actions:
            clicked = ax_perform(ref, "AXConfirm")

    if pos and size:
        cx, cy = pos[0] + size[0] // 2, pos[1] + size[1] // 2
        at = [cx, cy]
        if double:
            raw_input.double_click(cx, cy)
            clicked = True
        elif right:
            raw_input.right_click(cx, cy)
            clicked = True
        elif not clicked:
            raw_input.click(cx, cy)
            clicked = True

    if clicked:
        clean = {k: v for k, v in target.items() if not k.startswith("_")}
        return {"ok": True, "action": "click_spatial", "element": clean, "at": at}

    return {"ok": False, "error": "Found element but could not click it"}


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

    if lower in ("maximize", "maximize window", "fullscreen"):
        return native.maximize_window()

    # --- Synonym expansion (after shortcuts/getters, before verb dispatch) ---
    action = _normalize_action(action)
    lower = action.lower()

    # --- Verb-based intents ---
    verb, _, rest = action.partition(" ")
    verb = verb.lower()
    rest = rest.strip()

    # Menu paths: "click File > Save" or "menu File > Save"
    if verb in ("click", "menu") and ">" in rest:
        return native.click_menu(rest, pid=pid)

    if verb == "click":
        return _handle_click(rest, pid=pid)

    if verb in ("double-click", "doubleclick", "dblclick"):
        return _handle_click(rest, double=True, pid=pid)

    if verb in ("right-click", "rightclick", "rclick"):
        return _handle_click(rest, right=True, pid=pid)

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
        return _handle_scroll(rest)

    if verb == "focus":
        return native.focus_element(rest, pid=pid)

    if verb == "drag":
        return _handle_drag(rest)

    if verb == "tile":
        return _handle_tile(rest)

    if verb in ("move", "position"):
        return _handle_move(rest)

    if verb == "menu":
        return native.click_menu(rest, pid=pid)

    if verb == "fill":
        return _handle_fill(rest, pid=pid)

    if verb == "wait":
        return _handle_wait(rest, pid=pid)

    if verb == "notify":
        return native.notify("Nexus", rest)

    if verb == "say":
        return native.say(rest)

    if verb in ("navigate", "goto", "go"):
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


def _run_chain(action, pid=None):
    """Execute a semicolon-separated chain of actions sequentially.

    Stops at the first failure and reports which step failed.
    Returns a summary of all completed steps + the failure (if any).
    """
    import time

    steps = [s.strip() for s in action.split(";") if s.strip()]
    if not steps:
        return {"ok": False, "error": "Empty action chain"}

    results = []
    for i, step in enumerate(steps):
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


def _handle_click(target, double=False, right=False, pid=None):
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

    # Check for ordinal reference: "the 2nd button", "3rd link", "last checkbox"
    ordinal = _parse_ordinal(target)
    if ordinal:
        return _click_nth(ordinal, double=double, right=right, pid=pid)

    # Check for spatial reference: "button near search", "field below Username"
    spatial = _parse_spatial(target)
    if spatial:
        return _click_spatial(spatial, double=double, right=right, pid=pid)

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

    result = native.click_element(target, pid=pid, role=role)

    # If native click worked but we need double/right click, use coordinates
    if result.get("ok") and (double or right):
        at = result.get("at")
        if at:
            if double:
                raw_input.double_click(at[0], at[1])
            elif right:
                raw_input.right_click(at[0], at[1])

    return result


def _click_nth(ordinal_info, double=False, right=False, pid=None):
    """Click the nth element matching a role (and optional label).

    Args:
        ordinal_info: tuple (ordinal, role, label) from _parse_ordinal.
        pid: Target app PID (default: frontmost app).
    """
    from nexus.sense.access import describe_app, ax_actions, ax_perform

    n, role, label = ordinal_info

    # Map user-facing role names to raw AXRole values (locale-independent)
    ROLE_MAP = {
        "button": "AXButton", "link": "AXLink", "tab": "AXTab",
        "menu": "AXMenuItem", "field": "AXTextField", "checkbox": "AXCheckBox",
        "radio": "AXRadioButton", "text": "AXStaticText", "image": "AXImage",
        "slider": "AXSlider", "switch": "AXSwitch", "toggle": "AXSwitch",
    }
    ax_role = ROLE_MAP.get(role)

    elements = describe_app(pid)

    # Filter by raw AXRole (locale-independent) — falls back to display role
    if ax_role:
        matches = [el for el in elements if el.get("_ax_role") == ax_role]
    else:
        matches = [el for el in elements if role in el.get("role", "").lower()]

    # Filter by label if provided
    if label:
        label_lower = label.lower()
        labeled = [el for el in matches if label_lower in el.get("label", "").lower()]
        if labeled:
            matches = labeled

    if not matches:
        # Count elements by role for better feedback
        role_counts = {}
        for el in elements:
            r = el.get("role", "?")
            role_counts[r] = role_counts.get(r, 0) + 1
        role_summary = [f"{count} {r}" for r, count in sorted(role_counts.items(), key=lambda x: -x[1])[:8]]
        return {
            "ok": False,
            "error": f'No {role}s found' + (f' matching "{label}"' if label else ''),
            "found_roles": role_summary,
            "available": [f'{el["role"]}: {el.get("label", "")}' for el in elements[:15]],
        }

    # Resolve ordinal (-1 = last)
    if n == -1:
        idx = len(matches) - 1
    else:
        idx = n - 1  # 1-based to 0-based

    if idx < 0 or idx >= len(matches):
        return {
            "ok": False,
            "error": f'Requested {role} #{n} but only {len(matches)} found',
        }

    target = matches[idx]
    ref = target.get("_ref")
    if not ref:
        return {"ok": False, "error": "No element reference"}

    # Click via AX action
    actions = ax_actions(ref)
    clicked = False
    if "AXPress" in actions:
        clicked = ax_perform(ref, "AXPress")
    elif "AXConfirm" in actions:
        clicked = ax_perform(ref, "AXConfirm")

    # Handle double/right click or fallback to coordinates
    pos = target.get("pos")
    size = target.get("size")
    if pos and size:
        cx, cy = pos[0] + size[0] // 2, pos[1] + size[1] // 2
        if double:
            raw_input.double_click(cx, cy)
            clicked = True
        elif right:
            raw_input.right_click(cx, cy)
            clicked = True
        elif not clicked:
            raw_input.click(cx, cy)
            clicked = True

    if clicked:
        clean = {k: v for k, v in target.items() if not k.startswith("_")}
        return {
            "ok": True,
            "action": f"click_{role}_{n}",
            "element": clean,
            "at": [cx, cy] if pos and size else None,
            "ordinal": n,
            "of_total": len(matches),
        }

    return {"ok": False, "error": f'Found {role} #{n} but could not click it'}


def _handle_type(rest, pid=None):
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
        return native.set_value(target, text, pid=pid)

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


def _handle_wait(rest, pid=None):
    """Handle wait intents.

    Patterns:
        wait for <target>                — poll until element appears (10s timeout)
        wait for <target> <N>s           — poll with custom timeout
        wait until <target> disappears   — poll until element is gone
        wait <N>                         — sleep N seconds
        wait <N>s                        — sleep N seconds
    """
    import time
    from nexus.sense.access import find_elements

    if not rest:
        return {"ok": False, "error": "Wait for what? E.g.: wait for Save dialog, wait 2s"}

    lower = rest.lower().strip()

    # Simple delay: "wait 2", "wait 2s", "wait 2 seconds", "wait 500ms"
    delay_match = re.match(r"^(\d+(?:\.\d+)?)\s*(s|seconds?|ms)?$", lower)
    if delay_match:
        amount = float(delay_match.group(1))
        unit = delay_match.group(2) or "s"
        if unit == "ms":
            amount /= 1000
        amount = min(amount, 30)  # Cap at 30 seconds
        time.sleep(amount)
        return {"ok": True, "action": "wait", "seconds": amount}

    # Wait until disappears: "wait until Save disappears"
    disappear_match = re.match(
        r"until\s+(.+?)\s+(?:disappears?|goes?\s+away|is\s+gone|vanishes?)$",
        lower,
    )
    if disappear_match:
        target = disappear_match.group(1).strip()
        return _poll_for(target, appear=False, pid=pid)

    # Wait for element: "wait for Save dialog", "wait for Save dialog 5s"
    for_match = re.match(r"for\s+(.+?)(?:\s+(\d+)s)?$", rest.strip(), re.IGNORECASE)
    if for_match:
        target = for_match.group(1).strip()
        timeout = int(for_match.group(2)) if for_match.group(2) else 10
        return _poll_for(target, appear=True, timeout=timeout, pid=pid)

    # Fallback: treat as "wait for <rest>"
    return _poll_for(rest, appear=True, pid=pid)


def _poll_for(target, appear=True, timeout=10, interval=0.5, pid=None):
    """Poll until an element appears or disappears.

    Args:
        target: Element label/text to search for.
        appear: If True, wait for it to appear. If False, wait for it to vanish.
        timeout: Max seconds to wait.
        interval: Seconds between polls.
        pid: Target app PID (default: frontmost app).

    Returns:
        dict with result.
    """
    import time
    from nexus.sense.access import find_elements

    deadline = time.time() + min(timeout, 30)
    polls = 0

    while time.time() < deadline:
        matches = find_elements(target, pid)
        found = len(matches) > 0
        polls += 1

        if appear and found:
            el = matches[0]
            clean = {k: v for k, v in el.items() if not k.startswith("_")}
            return {
                "ok": True,
                "action": "wait_found",
                "element": clean,
                "polls": polls,
                "waited": round(polls * interval, 1),
            }

        if not appear and not found:
            return {
                "ok": True,
                "action": "wait_gone",
                "target": target,
                "polls": polls,
                "waited": round(polls * interval, 1),
            }

        time.sleep(interval)

    # Timeout
    verb = "appear" if appear else "disappear"
    return {
        "ok": False,
        "error": f'Timeout ({timeout}s): "{target}" did not {verb}',
        "polls": polls,
    }


def _handle_fill(rest, pid=None):
    """Handle fill intents: 'fill Name=Ferran, Email=f@x.com'.

    Parses comma-separated key=value pairs, finds each field by label,
    and sets its value. Reports per-field success/failure.

    Also supports:
        fill form Name=Ferran, Email=f@x.com  (leading "form" is stripped)
    """
    if not rest:
        return {"ok": False, "error": 'Fill format: fill Name=value, Email=value'}

    # Strip optional leading "form" or "in"
    stripped = rest
    for prefix in ("form ", "in "):
        if stripped.lower().startswith(prefix):
            stripped = stripped[len(prefix):]
            break

    # Parse key=value pairs (comma-separated)
    pairs = _parse_fields(stripped)
    if not pairs:
        return {"ok": False, "error": f'Could not parse fields from: "{rest}"'}

    import time
    results = []
    errors = []

    for field_name, field_value in pairs:
        result = native.set_value(field_name, field_value, pid=pid)
        if result.get("ok"):
            results.append(f'{field_name} = "{field_value}"')
        else:
            errors.append(f'{field_name}: {result.get("error", "failed")}')
        time.sleep(0.1)  # Brief pause between fields for UI to settle

    if errors:
        return {
            "ok": False,
            "action": "fill",
            "filled": results,
            "errors": errors,
            "error": f'Failed on {len(errors)} field(s): {", ".join(errors)}',
        }

    return {
        "ok": True,
        "action": "fill",
        "filled": results,
        "count": len(results),
    }


def _parse_fields(text):
    """Parse 'Name=Ferran, Email=f@x.com' into [(key, value), ...].

    Handles quoted values: Name="John Doe", Age=30
    """
    pairs = []
    # Split on comma, but respect quotes
    parts = re.split(r',\s*(?=[^"]*(?:"[^"]*"[^"]*)*$)', text)

    for part in parts:
        part = part.strip()
        if not part:
            continue
        eq = part.find("=")
        if eq == -1:
            continue
        key = part[:eq].strip()
        value = part[eq + 1:].strip()
        value = _strip_quotes(value)
        if key:
            pairs.append((key, value))

    return pairs


def _strip_quotes(text):
    """Strip surrounding quotes if present."""
    if len(text) >= 2:
        if (text[0] == '"' and text[-1] == '"') or (text[0] == "'" and text[-1] == "'"):
            return text[1:-1]
    return text


# ---------------------------------------------------------------------------
# CDP actions — browser navigation, JS execution
# ---------------------------------------------------------------------------

def _handle_navigate(rest):
    """Handle: navigate to https://..., goto google.com."""
    url = rest.strip()
    # Strip optional "to"
    if url.lower().startswith("to "):
        url = url[3:].strip()

    url = _strip_quotes(url)

    # Add https:// if no scheme
    if url and not url.startswith(("http://", "https://", "file://")):
        url = "https://" + url

    if not url:
        return {"ok": False, "error": "No URL specified"}

    try:
        from nexus.sense.web import ensure_cdp, navigate
        cdp = ensure_cdp()
        if cdp["available"]:
            return navigate(url)
    except Exception:
        pass

    # Fallback: open URL via AppleScript in default browser
    return native.run_applescript(f'open location "{url}"')


def _handle_run_js(expression):
    """Handle: run js document.title, js alert('hi')."""
    expression = expression.strip()
    if not expression:
        return {"ok": False, "error": "No JavaScript expression"}

    expression = _strip_quotes(expression)

    try:
        from nexus.sense.web import ensure_cdp, run_js
        cdp = ensure_cdp()
        if not cdp["available"]:
            msg = cdp.get("message", "CDP not available")
            return {"ok": False, "error": msg}
        result = run_js(expression)
        if result.get("ok"):
            value = result.get("value")
            return {
                "ok": True,
                "action": "run_js",
                "text": str(value) if value is not None else "(undefined)",
            }
        return result
    except Exception as e:
        return {"ok": False, "error": f"JS execution failed: {e}"}


# ---------------------------------------------------------------------------
# CDP tab management — switch, new, close tabs in Chrome
# ---------------------------------------------------------------------------

def _handle_switch_tab(rest):
    """Handle: switch tab 2, switch to tab Google."""
    try:
        from nexus.sense.web import ensure_cdp, switch_tab
        cdp = ensure_cdp()
        if not cdp["available"]:
            return {"ok": False, "error": cdp.get("message", "CDP not available")}

        identifier = rest.strip() if rest.strip() else 1
        # Try numeric index
        if isinstance(identifier, str) and identifier.isdigit():
            identifier = int(identifier)
        return switch_tab(identifier)
    except Exception as e:
        return {"ok": False, "error": f"Tab switch failed: {e}"}


def _handle_new_tab(rest):
    """Handle: new tab, new tab google.com."""
    try:
        from nexus.sense.web import ensure_cdp, new_tab
        cdp = ensure_cdp()
        if not cdp["available"]:
            return {"ok": False, "error": cdp.get("message", "CDP not available")}

        url = rest.strip() if rest.strip() else None
        if url:
            url = _strip_quotes(url)
            if not url.startswith(("http://", "https://", "file://")):
                url = "https://" + url
        return new_tab(url)
    except Exception as e:
        return {"ok": False, "error": f"New tab failed: {e}"}


def _handle_close_tab(rest):
    """Handle: close tab, close tab 3, close tab Google."""
    try:
        from nexus.sense.web import ensure_cdp, close_tab
        cdp = ensure_cdp()
        if not cdp["available"]:
            return {"ok": False, "error": cdp.get("message", "CDP not available")}

        identifier = rest.strip() if rest.strip() else None
        if identifier and identifier.isdigit():
            identifier = int(identifier)
        return close_tab(identifier)
    except Exception as e:
        return {"ok": False, "error": f"Close tab failed: {e}"}
