"""Window management intents — tile, move, minimize, restore, resize, fullscreen."""

import re
from nexus.act import native
from nexus.state import emit


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
    """Handle window positioning intents.

    Patterns:
        move window left/right/center/full    — halves / center / maximize
        move window top/bottom                — top / bottom half
        move window top-left/top-right/...    — quarters
        move window left-third/center-third/right-third — thirds
        move Safari left                      — named app
        move Safari to 100,200                — position at coordinates
        move window 2 left                    — specific window index
    """
    lower = rest.lower().strip()
    from nexus.act.input import screen_size
    sz = screen_size()
    sw, sh = sz["width"], sz["height"]
    menu_y = 25
    usable_h = sh - menu_y
    half_w = sw // 2
    half_h = usable_h // 2
    third_w = sw // 3

    app_name = None
    window_index = 1
    direction = lower

    # Check for "window N <direction>"
    win_idx_match = re.match(r"window\s+(\d+)\s+(.+)$", lower)
    if win_idx_match:
        window_index = int(win_idx_match.group(1))
        direction = win_idx_match.group(2).strip()
    else:
        # Check for coordinate move: "[app] to X,Y"
        coord_match = re.match(r"(?:(.+?)\s+)?to\s+(\d+)\s*[,\s]\s*(\d+)", rest.strip(), re.IGNORECASE)
        if coord_match:
            candidate = coord_match.group(1)
            x, y = int(coord_match.group(2)), int(coord_match.group(3))
            if candidate and candidate.lower() != "window":
                app_name = candidate
            return native.move_window(app_name, x=x, y=y, window_index=window_index)

        words = lower.split()
        if len(words) >= 2:
            direction = words[-1]
            candidate = " ".join(words[:-1])
            if candidate != "window":
                app_name = candidate

    # Grid positions
    grid = {
        # Halves (left/right existing, top/bottom new)
        "left": (0, menu_y, half_w, usable_h),
        "l": (0, menu_y, half_w, usable_h),
        "right": (half_w, menu_y, half_w, usable_h),
        "r": (half_w, menu_y, half_w, usable_h),
        "top": (0, menu_y, sw, half_h),
        "bottom": (0, menu_y + half_h, sw, half_h),
        # Quarters
        "top-left": (0, menu_y, half_w, half_h),
        "topleft": (0, menu_y, half_w, half_h),
        "top-right": (half_w, menu_y, half_w, half_h),
        "topright": (half_w, menu_y, half_w, half_h),
        "bottom-left": (0, menu_y + half_h, half_w, half_h),
        "bottomleft": (0, menu_y + half_h, half_w, half_h),
        "bottom-right": (half_w, menu_y + half_h, half_w, half_h),
        "bottomright": (half_w, menu_y + half_h, half_w, half_h),
        # Thirds
        "left-third": (0, menu_y, third_w, usable_h),
        "leftthird": (0, menu_y, third_w, usable_h),
        "center-third": (third_w, menu_y, third_w, usable_h),
        "centerthird": (third_w, menu_y, third_w, usable_h),
        "middle-third": (third_w, menu_y, third_w, usable_h),
        "right-third": (2 * third_w, menu_y, third_w, usable_h),
        "rightthird": (2 * third_w, menu_y, third_w, usable_h),
        # Center (existing)
        "center": (sw // 4, menu_y, half_w, usable_h),
        "centre": (sw // 4, menu_y, half_w, usable_h),
        "c": (sw // 4, menu_y, half_w, usable_h),
    }

    if direction in ("full", "max", "maximize"):
        return native.maximize_window(app_name)

    if direction in grid:
        x, y, w, h = grid[direction]
        return native.move_window(app_name, x=x, y=y, w=w, h=h, window_index=window_index)

    return {
        "ok": False,
        "error": (
            f"Unknown position: {direction}. Use: left, right, top, bottom, "
            "top-left, top-right, bottom-left, bottom-right, "
            "left-third, center-third, right-third, center, full"
        ),
    }


def _handle_minimize(rest):
    """Handle: 'minimize', 'minimize Safari', 'minimize window 2'."""
    if not rest:
        return native.minimize_window()

    lower = rest.lower().strip()

    # "minimize window 2" or "minimize window 2 of Safari"
    win_idx_match = re.match(r"window\s+(\d+)(?:\s+(?:of\s+)?(.+))?$", lower)
    if win_idx_match:
        idx = int(win_idx_match.group(1))
        app_name = win_idx_match.group(2) if win_idx_match.group(2) else None
        return native.minimize_window(app_name=app_name, window_index=idx)

    # "minimize window" (no index)
    if lower == "window":
        return native.minimize_window()

    # "minimize Safari"
    return native.minimize_window(app_name=rest.strip())


def _handle_restore(rest):
    """Handle: 'restore', 'restore Safari', 'unminimize Chrome'."""
    if not rest:
        return native.unminimize_window()

    if rest.lower().strip() == "window":
        return native.unminimize_window()

    return native.unminimize_window(app_name=rest.strip())


def _handle_resize(rest, pid=None):
    """Handle resize intents.

    Patterns:
        resize to 800x600           — resize focused window
        resize 800x600              — same
        resize Safari to 800x600    — resize Safari
        resize to 50%               — resize to 50% of screen
        resize Safari to 75%        — resize Safari to 75% of screen
        resize window 2 to 800x600  — resize window #2
    """
    if not rest:
        return {"ok": False, "error": 'Resize format: "resize to 800x600" or "resize to 50%"'}

    from nexus.act.input import screen_size
    sz = screen_size()
    lower = rest.lower().strip()

    # Try "window N to ..." first
    win_idx_match = re.match(
        r"window\s+(\d+)\s+(?:to\s+)?(\d+)\s*[xX*,]\s*(\d+)", lower
    )
    if win_idx_match:
        idx = int(win_idx_match.group(1))
        w, h = int(win_idx_match.group(2)), int(win_idx_match.group(3))
        return native.resize_window(w=w, h=h, window_index=idx)

    # Split into app_name + dimensions via "to" keyword
    app_name = None
    dims_str = lower
    if " to " in lower:
        parts = lower.split(" to ", 1)
        candidate = parts[0].strip()
        dims_str = parts[1].strip()
        if candidate and candidate != "window":
            app_name = rest.strip().split(" to ", 1)[0].strip()  # Preserve case
    elif lower.startswith("to "):
        dims_str = lower[3:].strip()

    # Try percentage: N%
    pct_match = re.match(r"(\d+)\s*%$", dims_str)
    if pct_match:
        pct = int(pct_match.group(1))
        w = int(sz["width"] * pct / 100)
        h = int((sz["height"] - 25) * pct / 100)
        return native.resize_window(app_name=app_name, w=w, h=h)

    # Try absolute: WxH (or W,H or W*H)
    abs_match = re.match(r"(\d+)\s*[xX*,]\s*(\d+)$", dims_str)
    if abs_match:
        w, h = int(abs_match.group(1)), int(abs_match.group(2))
        return native.resize_window(app_name=app_name, w=w, h=h)

    return {"ok": False, "error": f'Could not parse resize dimensions from: "{rest}"'}


def _handle_fullscreen(rest):
    """Handle: 'fullscreen Safari', 'fullscreen', 'exit fullscreen'."""
    if not rest:
        return native.fullscreen_window()

    if rest.lower().strip() == "window":
        return native.fullscreen_window()

    return native.fullscreen_window(app_name=rest.strip())


def _list_windows():
    """List all visible on-screen windows with their positions."""
    from nexus.sense.access import windows
    wins = windows()
    if not wins:
        return {"ok": True, "action": "list_windows", "text": "No windows found."}

    lines = []
    for i, w in enumerate(wins, 1):
        b = w["bounds"]
        title = f' — "{w["title"]}"' if w.get("title") else ""
        lines.append(f"  {i}. {w['app']}{title}  [{b['w']}x{b['h']} at {b['x']},{b['y']}]")

    header = f"{len(wins)} windows on screen:"
    return {"ok": True, "action": "list_windows", "count": len(wins), "text": header + "\n" + "\n".join(lines)}
