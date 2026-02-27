"""Intent handlers — type, press, scroll, hover, drag, fill, wait, observe, CDP, data."""

import re
from nexus.act import native, input as raw_input
from nexus.act.parse import _strip_quotes, _parse_fields, KEY_ALIASES
from nexus.state import emit


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
    # Try AX set_value on focused element first (proper focus + value setting),
    # then fall back to raw input (pyautogui / clipboard paste).
    text = _strip_quotes(rest)
    try:
        from nexus.sense.access import focused_element, ax_set
        focused = focused_element(pid=pid)
        if focused and focused.get("_ref"):
            ref = focused["_ref"]
            ax_set(ref, "AXFocused", True)
            if ax_set(ref, "AXValue", text):
                return {"ok": True, "action": "set_value", "text": text}
    except Exception:
        pass
    raw_input.type_text(text)
    return {"ok": True, "action": "type", "text": text}


def _handle_press(keys_str, pid=None):
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


def _handle_scroll(direction, pid=None):
    """Handle scroll intents.

    Patterns:
        scroll down                     → scroll 3 clicks down
        scroll up 5                     → scroll 5 clicks up
        scroll down in <element>        → scroll at element center
        scroll until <target>           → scroll down until target appears
        scroll until <target> appears   → same
    """
    rest = direction.strip()
    lower = rest.lower()

    # "scroll until X appears" / "scroll until X"
    until_match = re.match(r"until\s+(.+?)(?:\s+appears?)?\s*$", lower, re.IGNORECASE)
    if until_match:
        target = until_match.group(1).strip()
        return _scroll_until(target, pid=pid)

    # "scroll down in <element>" / "scroll up in <element>"
    in_match = re.match(r"(down|up|d|u)(?:\s+(\d+))?\s+in\s+(.+)$", lower, re.IGNORECASE)
    if in_match:
        dir_word = in_match.group(1)
        amount = int(in_match.group(2)) if in_match.group(2) else 3
        element_name = in_match.group(3).strip()
        return _scroll_in_element(dir_word, amount, element_name, pid=pid)

    # Standard scroll: "scroll down", "scroll up 5", etc.
    amount = 3
    parts = lower.split()
    if len(parts) >= 2 and parts[-1].isdigit():
        amount = int(parts[-1])
        direction = parts[0]
    else:
        direction = lower

    if direction in ("down", "d"):
        return raw_input.scroll(-amount)
    elif direction in ("up", "u"):
        return raw_input.scroll(amount)
    elif direction in ("left", "l"):
        raw_input.hotkey("shift", "scroll")
        return {"ok": True, "action": "scroll_left", "note": "horizontal scroll may not work everywhere"}
    elif direction in ("right", "r"):
        return {"ok": True, "action": "scroll_right", "note": "horizontal scroll may not work everywhere"}
    else:
        return raw_input.scroll(-amount)  # Default: down


def _scroll_in_element(direction, amount, element_name, pid=None):
    """Scroll at the center of a named element (e.g. a list or panel)."""
    from nexus.sense.access import find_elements

    matches = find_elements(element_name, pid)
    if not matches:
        return {"ok": False, "error": f'Scroll target "{element_name}" not found'}

    el = matches[0]
    pos = el.get("pos")
    size = el.get("size")
    if not pos or not size:
        return {"ok": False, "error": f'Element "{element_name}" has no position'}

    cx = pos[0] + size[0] // 2
    cy = pos[1] + size[1] // 2

    clicks = -amount if direction in ("down", "d") else amount
    return raw_input.scroll(clicks, x=cx, y=cy)


def _scroll_until(target, direction="down", max_scrolls=20, pid=None):
    """Scroll until a target element appears on screen.

    Scrolls in the given direction, checking after each scroll whether
    the target element is now visible. Gives up after max_scrolls.
    """
    import time
    from nexus.sense.access import find_elements

    clicks_per_scroll = 3
    scroll_amount = -clicks_per_scroll if direction == "down" else clicks_per_scroll

    for i in range(max_scrolls):
        emit(f"Scroll until '{target}'... ({i+1}/{max_scrolls})")
        matches = find_elements(target, pid)
        if matches:
            el = matches[0]
            clean = {k: v for k, v in el.items() if not k.startswith("_")}
            return {
                "ok": True,
                "action": "scroll_until",
                "element": clean,
                "scrolls": i,
                "direction": direction,
            }
        raw_input.scroll(scroll_amount)
        time.sleep(0.3)

    return {
        "ok": False,
        "error": f'"{target}" not found after {max_scrolls} scrolls {direction}',
        "scrolls": max_scrolls,
    }


def _handle_hover(rest, pid=None):
    """Handle hover intents: 'hover Save', 'hover over the search field'.

    Moves mouse to element center without clicking. Useful for tooltips,
    hover menus, and preview effects.
    """
    if not rest:
        return {"ok": False, "error": "Hover over what? E.g.: hover Save, hover over search"}

    target = rest.strip()
    # Strip "over" prefix: "hover over Save" → "Save"
    if target.lower().startswith("over "):
        target = target[5:].strip()
    if target.lower().startswith("the "):
        target = target[4:].strip()

    # Check for coordinate hover: "hover 340,220"
    coord_match = re.match(r"(?:at\s+)?(\d+)[,\s]+(\d+)", target)
    if coord_match:
        x, y = int(coord_match.group(1)), int(coord_match.group(2))
        return raw_input.hover(x, y)

    # Find element and hover its center
    from nexus.sense.access import find_elements
    matches = find_elements(target, pid)
    if not matches:
        return {"ok": False, "error": f'Element "{target}" not found for hover'}

    el = matches[0]
    pos = el.get("pos")
    size = el.get("size")
    if pos and size:
        cx, cy = pos[0] + size[0] // 2, pos[1] + size[1] // 2
        raw_input.hover(cx, cy)
        clean = {k: v for k, v in el.items() if not k.startswith("_")}
        return {"ok": True, "action": "hover", "element": clean, "at": [cx, cy]}

    return {"ok": False, "error": f'Element "{target}" has no position'}


def _handle_drag(rest, pid=None):
    """Handle drag intents: 'drag 100,200 to 300,400' or 'drag file.txt to Trash'.

    Supports both coordinate-based and element-name-based drag.
    """
    # Coordinate drag: "drag 100,200 to 300,400"
    match = re.match(r"(\d+)[,\s]+(\d+)\s+to\s+(\d+)[,\s]+(\d+)", rest)
    if match:
        x1, y1, x2, y2 = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
        return raw_input.drag(x1, y1, x2, y2)

    # Element-based drag: "drag file.txt to Trash"
    to_match = re.match(r"(.+?)\s+to\s+(.+)$", rest, re.IGNORECASE)
    if to_match:
        source_name = to_match.group(1).strip()
        target_name = to_match.group(2).strip()

        from nexus.sense.access import find_elements
        src_matches = find_elements(source_name, pid)
        if not src_matches:
            return {"ok": False, "error": f'Drag source "{source_name}" not found'}

        tgt_matches = find_elements(target_name, pid)
        if not tgt_matches:
            return {"ok": False, "error": f'Drag target "{target_name}" not found'}

        src = src_matches[0]
        tgt = tgt_matches[0]
        sp, ss = src.get("pos"), src.get("size")
        tp, ts = tgt.get("pos"), tgt.get("size")

        if sp and ss and tp and ts:
            x1 = sp[0] + ss[0] // 2
            y1 = sp[1] + ss[1] // 2
            x2 = tp[0] + ts[0] // 2
            y2 = tp[1] + ts[1] // 2
            raw_input.drag(x1, y1, x2, y2)
            return {
                "ok": True, "action": "drag",
                "from_element": source_name, "to_element": target_name,
                "from": [x1, y1], "to": [x2, y2],
            }
        return {"ok": False, "error": "Found elements but missing positions"}

    return {"ok": False, "error": "Drag format: 'drag x1,y1 to x2,y2' or 'drag Source to Target'"}


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


# ---------------------------------------------------------------------------
# Wait / observe / poll
# ---------------------------------------------------------------------------

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


def _handle_observe(rest, pid=None):
    """Handle observe start/stop/clear/status intents."""
    from nexus.sense.observe import start_observing, stop_observing, drain_events, is_observing, status
    from nexus.sense.access import frontmost_app

    cmd = rest.strip().lower() if rest else "start"

    if cmd in ("start", "on", "begin", ""):
        if pid is None:
            app = frontmost_app()
            if not app:
                return {"ok": False, "error": "No frontmost app to observe"}
            pid = app["pid"]
            app_name = app["name"]
        else:
            app_name = ""
        return start_observing(pid, app_name)

    if cmd in ("stop", "off", "end"):
        return stop_observing(pid)

    if cmd in ("clear", "flush", "reset"):
        drain_events()
        return {"ok": True, "action": "observe_clear"}

    if cmd in ("status", "info"):
        return status()

    return {"ok": False, "error": f'Unknown observe command: "{rest}". Use: start, stop, clear, status'}


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
        elapsed = round(time.time() - (deadline - min(timeout, 30)), 1)
        verb = "appear" if appear else "disappear"
        emit(f"Waiting for '{target}' to {verb}... ({elapsed}s / {timeout}s)")
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


# ---------------------------------------------------------------------------
# Structured data getters — tables and lists
# ---------------------------------------------------------------------------

def _handle_read_table(pid=None):
    """Read all tables in the focused window as structured data."""
    from nexus.sense.access import find_tables
    tables = find_tables(pid)
    if not tables:
        return {"ok": True, "action": "read_table", "text": "No tables found on screen."}

    parts = []
    for tbl in tables:
        title = tbl.get("title", "")
        headers = tbl.get("headers", [])
        rows = tbl.get("rows", [])
        title_part = f' "{title}"' if title else ""
        parts.append(f'Table{title_part}: {tbl["num_cols"]} columns, {tbl["num_rows"]} rows')
        if headers:
            parts.append(f'  Headers: {" | ".join(headers)}')
        for i, row in enumerate(rows[:30]):
            parts.append(f'  Row {i+1}: {" | ".join(str(c) for c in row)}')
        if len(rows) > 30:
            parts.append(f'  ... and {len(rows) - 30} more rows')

    return {"ok": True, "action": "read_table", "text": "\n".join(parts)}


def _handle_read_list(pid=None):
    """Read all lists in the focused window as structured data."""
    from nexus.sense.access import find_lists
    lists = find_lists(pid)
    if not lists:
        return {"ok": True, "action": "read_list", "text": "No lists found on screen."}

    parts = []
    for lst in lists:
        title = lst.get("title", "")
        items = lst.get("items", [])
        title_part = f' "{title}"' if title else ""
        parts.append(f'List{title_part}: {lst["count"]} items')
        for item in items[:30]:
            idx = item["index"] + 1
            label = item.get("label", "")
            sel = " *selected*" if item.get("selected") else ""
            parts.append(f'  {idx}. {label}{sel}')
        if len(items) > 30:
            parts.append(f'  ... and {len(items) - 30} more items')

    return {"ok": True, "action": "read_list", "text": "\n".join(parts)}


# ---------------------------------------------------------------------------
# Path navigation — click through UI hierarchies in a single intent
# ---------------------------------------------------------------------------

def _handle_path_nav(path, pid=None):
    """Navigate through a UI path by clicking each step sequentially.

    Example: "General > About" clicks "General", waits, clicks "About".
    Unlike menu paths, this clicks UI elements (sidebar items, tabs, etc.).

    Returns dict with navigation result.
    """
    import time

    steps = [s.strip() for s in path.split(">") if s.strip()]
    if not steps:
        return {"ok": False, "error": "Empty path"}

    for i, step in enumerate(steps):
        emit(f"Path step {i+1}/{len(steps)}: {step}")
        result = native.click_element(step, pid=pid)

        if not result.get("ok"):
            return {
                "ok": False,
                "action": "path_nav",
                "error": f'Step {i+1} failed: "{step}" — {result.get("error", "")}',
                "completed": i,
                "total": len(steps),
                "path": " > ".join(steps),
            }

        # Wait for UI to update between steps (content needs to load)
        if i < len(steps) - 1:
            time.sleep(0.3)
            from nexus.sense.access import invalidate_cache
            invalidate_cache()
            try:
                from nexus.mind.session import mark_dirty
                mark_dirty()  # All PIDs — layout is changing
            except Exception:
                pass

    return {
        "ok": True,
        "action": "path_nav",
        "completed": len(steps),
        "total": len(steps),
        "path": " > ".join(steps),
    }


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


def _handle_get_console(rest=""):
    """Handle: get console, console logs — retrieve browser console messages."""
    try:
        from nexus.sense.web import ensure_cdp, get_console_logs
        cdp = ensure_cdp()
        if not cdp["available"]:
            return {"ok": False, "error": cdp.get("message", "CDP not available")}

        limit = 20
        if rest.strip().isdigit():
            limit = int(rest.strip())
        result = get_console_logs(limit=limit)
        if not result.get("ok"):
            return result
        messages = result.get("messages", [])
        if not messages:
            return {"ok": True, "text": "No console messages captured yet. Messages will appear after console.log/warn/error calls."}
        lines = []
        for msg in messages:
            level = msg.get("level", "log").upper()
            text = msg.get("message", "")[:200]
            lines.append(f"  [{level}] {text}")
        return {"ok": True, "text": f"Console ({len(messages)} messages):\n" + "\n".join(lines)}
    except Exception as e:
        return {"ok": False, "error": f"Console capture failed: {e}"}
