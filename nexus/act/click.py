"""Click resolution — spatial, ordinal, container, and region clicking."""

import re
import time as _time
from nexus.act import native, input as raw_input
from nexus.act.parse import (
    ROLE_MAP, ROLE_WORDS,
    _parse_ordinal, _parse_spatial, _parse_container,
    _filter_by_search, _resolve_modifiers,
)
from nexus.state import emit


# ---------------------------------------------------------------------------
# Keyboard shortcut cache — prefer shortcuts over tree walking
# ---------------------------------------------------------------------------

_shortcut_cache = {}  # {pid: (timestamp, {label_lower: shortcut_string})}
_SHORTCUT_TTL = 60    # seconds — menus rarely change within a session


def _build_shortcut_cache(pid):
    """Build shortcut cache from app's menu bar. Returns {label_lower: shortcut}."""
    try:
        from nexus.sense.access import menu_bar
        items = menu_bar(pid)
        cache = {}
        for item in items:
            shortcut = item.get("shortcut")
            if not shortcut:
                continue
            # Store by title (e.g. "save" → "Cmd+S")
            title = item.get("title", "").strip().lower()
            if title and title not in cache:
                cache[title] = shortcut
        _shortcut_cache[pid] = (_time.time(), cache)
        return cache
    except Exception:
        return {}


def _try_shortcut(target, pid=None):
    """Check if a keyboard shortcut exists for the target label.

    Returns shortcut string (e.g. "Cmd+S") or None.
    Uses a 60s cache to avoid repeated menu bar walks.
    """
    if pid is None:
        from nexus.sense.access import frontmost_app
        info = frontmost_app()
        pid = info["pid"] if info else None
    if not pid:
        return None

    # Check cache
    if pid in _shortcut_cache:
        ts, cache = _shortcut_cache[pid]
        if _time.time() - ts < _SHORTCUT_TTL:
            return cache.get(target.strip().lower())

    # Build cache
    cache = _build_shortcut_cache(pid)
    return cache.get(target.strip().lower())


def _click_spatial(spatial_info, double=False, right=False, triple=False, modifiers=None, pid=None):
    """Click an element using spatial relationship to a reference element."""
    from nexus.sense.access import describe_app, find_elements

    search, relation, reference = spatial_info

    if relation == "region":
        return _click_in_region(search, reference, double=double, right=right, triple=triple, modifiers=modifiers, pid=pid)

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
    return _click_resolved(target, double=double, right=right, triple=triple, modifiers=modifiers)


def _click_in_region(search, region, double=False, right=False, triple=False, modifiers=None, pid=None):
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

    return _click_resolved(in_region[0], double=double, right=right, triple=triple, modifiers=modifiers)


def _click_resolved(target, double=False, right=False, triple=False, modifiers=None):
    """Click a resolved element dict. Used by spatial and region resolution."""
    from nexus.sense.access import ax_actions, ax_perform

    ref = target.get("_ref")
    pos = target.get("pos")
    size = target.get("size")

    clicked = False
    at = None

    if ref and not (double or right or triple or modifiers):
        actions = ax_actions(ref)
        if "AXPress" in actions:
            clicked = ax_perform(ref, "AXPress")
        elif "AXConfirm" in actions:
            clicked = ax_perform(ref, "AXConfirm")

    if pos and size:
        cx, cy = pos[0] + size[0] // 2, pos[1] + size[1] // 2
        at = [cx, cy]
        if modifiers:
            raw_input.modifier_click(cx, cy, _resolve_modifiers(modifiers))
            clicked = True
        elif triple:
            raw_input.triple_click(cx, cy)
            clicked = True
        elif double:
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
        result = {"ok": True, "action": "click_spatial", "element": clean, "at": at}
        if modifiers:
            result["modifiers"] = modifiers
        return result

    return {"ok": False, "error": "Found element but could not click it"}


# ---------------------------------------------------------------------------
# Container scoping — "click X in the row with/containing Y"
# ---------------------------------------------------------------------------

def _click_in_container(container_info, double=False, right=False, triple=False, modifiers=None, pid=None):
    """Click a target element inside a matching row.

    Finds the row (by text content or index), then searches within
    that row's subtree for the target element.
    """
    from nexus.sense.access import (
        find_tables, ax_attr, ax_actions, ax_perform, _cell_text,
    )

    target_name, row_match, row_index = container_info

    tables = find_tables(pid)
    if not tables:
        return {"ok": False, "error": "No tables found for container scoping"}

    # Search all tables for the matching row
    for tbl in tables:
        rows = tbl.get("rows", [])
        row_refs = tbl.get("row_refs", [])

        if row_index is not None:
            # By row number (1-based)
            idx = row_index - 1
            if 0 <= idx < len(row_refs):
                return _find_and_click_in_row(
                    row_refs[idx], target_name,
                    double=double, right=right, triple=triple, modifiers=modifiers,
                )
        elif row_match:
            # By content match — find the row containing the text
            match_lower = row_match.lower()
            for i, row_data in enumerate(rows):
                row_text = " ".join(str(cell) for cell in row_data).lower()
                if match_lower in row_text and i < len(row_refs):
                    return _find_and_click_in_row(
                        row_refs[i], target_name,
                        double=double, right=right, triple=triple, modifiers=modifiers,
                    )

    if row_index is not None:
        return {"ok": False, "error": f"Row {row_index} not found in any table"}
    return {"ok": False, "error": f'No row containing "{row_match}" found'}


def _find_and_click_in_row(row_ref, target_name, double=False, right=False, triple=False, modifiers=None):
    """Search within a row's subtree for an element matching target_name and click it."""
    from nexus.sense.access import ax_attr, walk_tree

    # Walk the row's subtree to find clickable children
    children = walk_tree(row_ref, max_depth=5, max_elements=50)

    target_lower = target_name.lower()

    # Check if target is a role word — "click button in row with Alice"
    ax_role = ROLE_MAP.get(target_lower)

    matches = []
    for el in children:
        if ax_role:
            if el.get("_ax_role") == ax_role:
                matches.append(el)
        else:
            label = el.get("label", "").lower()
            role = el.get("role", "").lower()
            if target_lower == label or target_lower in label or target_lower in role:
                matches.append(el)

    if not matches:
        available = [el.get("label", "") or el.get("role", "") for el in children]
        return {
            "ok": False,
            "error": f'"{target_name}" not found in the row',
            "available_in_row": [a for a in available if a][:10],
        }

    return _click_resolved(matches[0], double=double, right=right, triple=triple, modifiers=modifiers)


def _click_nth(ordinal_info, double=False, right=False, triple=False, modifiers=None, pid=None):
    """Click the nth element matching a role (and optional label).

    Args:
        ordinal_info: tuple (ordinal, role, label) from _parse_ordinal.
        pid: Target app PID (default: frontmost app).
    """
    from nexus.sense.access import describe_app, ax_actions, ax_perform

    n, role, label = ordinal_info
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

    # Click via AX action (skip for modifier/double/right/triple clicks)
    actions = ax_actions(ref)
    clicked = False
    if not (double or right or triple or modifiers):
        if "AXPress" in actions:
            clicked = ax_perform(ref, "AXPress")
        elif "AXConfirm" in actions:
            clicked = ax_perform(ref, "AXConfirm")

    # Handle modifier/double/right/triple click or fallback to coordinates
    pos = target.get("pos")
    size = target.get("size")
    at = None
    if pos and size:
        cx, cy = pos[0] + size[0] // 2, pos[1] + size[1] // 2
        at = [cx, cy]
        if modifiers:
            raw_input.modifier_click(cx, cy, _resolve_modifiers(modifiers))
            clicked = True
        elif triple:
            raw_input.triple_click(cx, cy)
            clicked = True
        elif double:
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
        result = {
            "ok": True,
            "action": f"click_{role}_{n}",
            "element": clean,
            "at": at,
            "ordinal": n,
            "of_total": len(matches),
        }
        if modifiers:
            result["modifiers"] = modifiers
        return result

    return {"ok": False, "error": f'Found {role} #{n} but could not click it'}


def _handle_click(target, double=False, right=False, triple=False, modifiers=None, pid=None):
    """Handle click intents."""
    if not target:
        # Click at current mouse position
        pos = raw_input.mouse_position()
        if triple:
            return raw_input.triple_click(pos["x"], pos["y"])
        if right:
            return raw_input.right_click(pos["x"], pos["y"])
        if double:
            return raw_input.double_click(pos["x"], pos["y"])
        return raw_input.click(pos["x"], pos["y"])

    # Check for coordinate click: "click 340,220" or "click at 340 220"
    coord_match = re.match(r"(?:at\s+)?(\d+)[,\s]+(\d+)", target)
    if coord_match:
        x, y = int(coord_match.group(1)), int(coord_match.group(2))
        if modifiers:
            return raw_input.modifier_click(x, y, _resolve_modifiers(modifiers))
        if triple:
            return raw_input.triple_click(x, y)
        if right:
            return raw_input.right_click(x, y)
        if double:
            return raw_input.double_click(x, y)
        return raw_input.click(x, y)

    # Check for ordinal reference: "the 2nd button", "3rd link", "last checkbox"
    ordinal = _parse_ordinal(target)
    if ordinal:
        n, role, label = ordinal
        emit(f"Resolving ordinal: {role} #{n}{'  ' + label if label else ''}...")
        return _click_nth(ordinal, double=double, right=right, triple=triple, modifiers=modifiers, pid=pid)

    # Check for container scoping: "delete in the row with Alice"
    container = _parse_container(target)
    if container:
        emit(f"Searching in container row for '{container[0]}'...")
        return _click_in_container(container, double=double, right=right, triple=triple, modifiers=modifiers, pid=pid)

    # Check for spatial reference: "button near search", "field below Username"
    spatial = _parse_spatial(target)
    if spatial:
        emit(f"Resolving spatial: '{spatial[0]}' {spatial[1]} '{spatial[2]}'...")
        return _click_spatial(spatial, double=double, right=right, triple=triple, modifiers=modifiers, pid=pid)

    # Keyboard shortcut preference — use shortcut instead of tree walk
    # Only for simple left-clicks without modifiers (shortcut IS the action)
    if not double and not right and not triple and not modifiers:
        shortcut = _try_shortcut(target, pid)
        if shortcut:
            emit(f"Using shortcut: {shortcut} (for '{target}')")
            keys = [k.strip().lower() for k in shortcut.split("+")]
            raw_input.hotkey(*keys)
            return {"ok": True, "action": "shortcut", "shortcut": shortcut,
                    "for": target}

    # Parse optional role filter: "click button Save" or "click Save button"
    role = None
    parts = target.split()
    if len(parts) >= 2:
        if parts[0].lower() in ROLE_WORDS:
            role = parts[0]
            target = " ".join(parts[1:])
        elif parts[-1].lower() in ROLE_WORDS:
            role = parts[-1]
            target = " ".join(parts[:-1])

    # For modifier clicks, we need coordinates — skip AX action, go straight to coordinate click
    if modifiers:
        from nexus.sense.access import find_elements
        matches = find_elements(target, pid)
        if role:
            role_lower = role.lower()
            ax_target = ROLE_MAP.get(role_lower)
            matches = [m for m in matches
                       if m.get("_ax_role") == ax_target or role_lower in m.get("role", "").lower()]
        if not matches:
            return {"ok": False, "error": f'Element "{target}" not found'}
        el = matches[0]
        pos, size = el.get("pos"), el.get("size")
        if pos and size:
            cx, cy = pos[0] + size[0] // 2, pos[1] + size[1] // 2
            raw_input.modifier_click(cx, cy, _resolve_modifiers(modifiers))
            clean = {k: v for k, v in el.items() if not k.startswith("_")}
            return {"ok": True, "action": "modifier_click", "element": clean,
                    "at": [cx, cy], "modifiers": modifiers}
        return {"ok": False, "error": f'Element "{target}" has no position'}

    emit(f"Searching for '{target}'...")
    result = native.click_element(target, pid=pid, role=role)

    # If element not found, try learned label translation (e.g. "Save" → "guardar")
    if not result.get("ok") and "not found" in result.get("error", "").lower():
        try:
            from nexus.mind.learn import lookup_label
            from nexus.act.resolve import _current_app_name
            app_name = _current_app_name(pid)
            mapped = lookup_label(target, app_name)
            if mapped and mapped.lower() != target.lower():
                emit(f"Retrying with learned label: {target} -> {mapped}")
                retry = native.click_element(mapped, pid=pid, role=role)
                if retry.get("ok"):
                    retry["via_label"] = f"{target} -> {mapped}"
                    return retry
        except Exception:
            pass

    # If native click worked but we need double/right/triple click, use coordinates
    if result.get("ok") and (double or right or triple):
        at = result.get("at")
        if at:
            if triple:
                raw_input.triple_click(at[0], at[1])
            elif double:
                raw_input.double_click(at[0], at[1])
            elif right:
                raw_input.right_click(at[0], at[1])

    return result
