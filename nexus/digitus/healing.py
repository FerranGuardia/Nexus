"""Digitus Healing — self-healing action recovery for Nexus.

When an action fails (element moved, window lost focus, timing issue),
automatically attempt recovery before returning an error to Claude.

Recovery pipeline:
  attempt_action → fail? → diagnose → recoverable? → apply fix → retry (max 2)
  → still failing? → return error + diagnosis + suggestions

Pure functions. No classes. Each recovery strategy is a function.
"""

import time

import pyautogui
import uiautomation as auto

from nexus.uia import element_to_dict, find_elements, collect_named_elements


# Max retry attempts for self-healing
MAX_RETRIES = 2

# Wait times in seconds
WAIT_FOREGROUND = 0.2
WAIT_ENABLED = 0.3
WAIT_ENABLED_MAX = 2.0
WAIT_POST_DISMISS = 0.3


# ---------------------------------------------------------------------------
# Failure diagnosis
# ---------------------------------------------------------------------------

def diagnose_click_failure(target_name: str, click_x: int, click_y: int,
                           role: str = None) -> dict:
    """Diagnose why a click action failed.

    Returns:
        {"failure_type": str, "recoverable": bool, "details": str,
         "recovery": str|None, ...}
    """
    fg = auto.GetForegroundControl()
    fg_title = fg.Name if fg else ""

    # Check what's at the click point
    over = auto.ControlFromPoint(click_x, click_y)
    over_dict = element_to_dict(over) if over else None

    # Try to re-find the target element
    matches = find_elements(fg, target_name)
    if role:
        from nexus.digitus.element import _filter_by_role
        matches = _filter_by_role(matches, role)

    # Case 1: element exists but moved
    if matches:
        new_target = matches[0]
        old_pos = (click_x, click_y)
        new_cx = new_target["bounds"]["center_x"]
        new_cy = new_target["bounds"]["center_y"]
        new_pos = (new_cx, new_cy)
        distance = ((old_pos[0] - new_pos[0]) ** 2 + (old_pos[1] - new_pos[1]) ** 2) ** 0.5

        if distance > 10:
            return {
                "failure_type": "element_moved",
                "recoverable": True,
                "recovery": "relocate",
                "details": "Element '%s' moved from (%d,%d) to (%d,%d)" % (
                    target_name, click_x, click_y, new_cx, new_cy),
                "new_x": new_cx,
                "new_y": new_cy,
                "distance": int(distance),
            }

        # Element is at same position — check if it's disabled
        if not new_target.get("is_enabled", True):
            return {
                "failure_type": "element_disabled",
                "recoverable": True,
                "recovery": "wait_enabled",
                "details": "Element '%s' exists but is disabled" % target_name,
            }

    # Case 2: dialog/popup blocking
    if over_dict:
        over_type = over_dict.get("type", "")
        over_name = over_dict.get("name", "")

        # Check if we clicked on a dialog overlay
        if over_type in ("WindowControl", "PaneControl") and over_name != fg_title:
            # Try to find dismiss buttons in the dialog
            dismiss_names = _find_dismiss_buttons(over)
            return {
                "failure_type": "dialog_blocking",
                "recoverable": bool(dismiss_names),
                "recovery": "dismiss_dialog" if dismiss_names else None,
                "details": "Dialog '%s' is blocking the target" % over_name,
                "dialog_name": over_name,
                "dismiss_options": dismiss_names,
            }

    # Case 3: element not found at all
    if not matches:
        # Check if window is still the same
        current_fg = auto.GetForegroundControl()
        current_title = current_fg.Name if current_fg else ""

        if current_title != fg_title:
            return {
                "failure_type": "window_changed",
                "recoverable": True,
                "recovery": "restore_window",
                "details": "Window changed from '%s' to '%s'" % (fg_title, current_title),
                "expected_window": fg_title,
                "current_window": current_title,
            }

        # Truly not found
        all_elements = collect_named_elements(fg)
        suggestions = _suggest_similar(target_name, all_elements)
        return {
            "failure_type": "element_not_found",
            "recoverable": False,
            "recovery": None,
            "details": "Element '%s' not found in current window" % target_name,
            "suggestions": suggestions,
        }

    # Case 4: unknown failure
    return {
        "failure_type": "unknown",
        "recoverable": False,
        "recovery": None,
        "details": "Click at (%d,%d) did not produce expected result" % (click_x, click_y),
    }


def _find_dismiss_buttons(dialog_ctrl) -> list[str]:
    """Find buttons in a dialog that could dismiss it (Close, Cancel, OK, X)."""
    dismiss_keywords = {"close", "cancel", "ok", "dismiss", "no", "x", "got it", "later"}
    matches = []
    try:
        for child in dialog_ctrl.GetChildren():
            name = (child.Name or "").strip().lower()
            ctrl_type = child.ControlTypeName
            if ctrl_type == "ButtonControl" and name:
                if name in dismiss_keywords or any(kw in name for kw in dismiss_keywords):
                    matches.append(child.Name)
    except Exception:
        pass
    return matches


def _suggest_similar(target: str, elements: list[dict]) -> list[str]:
    """Find elements with names similar to the target."""
    target_lower = target.lower()
    similar = []
    for el in elements:
        name = el.get("name", "")
        name_lower = name.lower()
        # Simple similarity: substring match or shared words
        if not name_lower:
            continue
        target_words = set(target_lower.split())
        name_words = set(name_lower.split())
        if target_words & name_words:
            similar.append(name)
        elif target_lower in name_lower or name_lower in target_lower:
            similar.append(name)
    return similar[:5]


# ---------------------------------------------------------------------------
# Recovery actions
# ---------------------------------------------------------------------------

def recover_relocate(target_name: str, new_x: int, new_y: int,
                     right: bool = False, double: bool = False) -> dict:
    """Re-click at the element's new position."""
    button = "right" if right else "left"
    clicks = 2 if double else 1
    pyautogui.click(new_x, new_y, clicks=clicks, button=button)
    return {
        "recovery": "relocate",
        "success": True,
        "clicked_at": {"x": new_x, "y": new_y},
    }


def recover_wait_enabled(target_name: str, role: str = None) -> dict:
    """Wait for an element to become enabled, then return its position."""
    waited = 0.0
    while waited < WAIT_ENABLED_MAX:
        time.sleep(WAIT_ENABLED)
        waited += WAIT_ENABLED

        fg = auto.GetForegroundControl()
        matches = find_elements(fg, target_name)
        if role:
            from nexus.digitus.element import _filter_by_role
            matches = _filter_by_role(matches, role)

        if matches and matches[0].get("is_enabled", True):
            target = matches[0]
            return {
                "recovery": "wait_enabled",
                "success": True,
                "waited_seconds": round(waited, 1),
                "x": target["bounds"]["center_x"],
                "y": target["bounds"]["center_y"],
            }

    return {
        "recovery": "wait_enabled",
        "success": False,
        "waited_seconds": round(waited, 1),
    }


def recover_restore_window(expected_title: str) -> dict:
    """Try to bring the expected window back to foreground."""
    import ctypes
    desktop = auto.GetRootControl()
    for child in desktop.GetChildren():
        name = child.Name or ""
        if expected_title.lower() in name.lower():
            handle = child.NativeWindowHandle
            if handle:
                ctypes.windll.user32.SetForegroundWindow(handle)
                time.sleep(WAIT_FOREGROUND)
                # Verify
                fg = auto.GetForegroundControl()
                if fg and expected_title.lower() in (fg.Name or "").lower():
                    return {"recovery": "restore_window", "success": True,
                            "window": fg.Name}
    return {"recovery": "restore_window", "success": False}


def recover_dismiss_dialog(dismiss_names: list[str]) -> dict:
    """Try to dismiss a blocking dialog by clicking a dismiss button."""
    # Try Escape first (universal dismiss)
    pyautogui.press("escape")
    time.sleep(WAIT_POST_DISMISS)

    # Check if dialog is gone
    fg = auto.GetForegroundControl()
    # If the dialog dismissed, the focused control should have changed
    focused = auto.GetFocusedControl()
    focused_name = focused.Name if focused else ""

    # If Escape worked, we're done
    # Simple heuristic: if focus is no longer on a dialog button
    if focused_name and focused_name not in dismiss_names:
        return {"recovery": "dismiss_dialog", "success": True,
                "method": "escape"}

    # Try clicking specific dismiss buttons
    for btn_name in dismiss_names:
        matches = find_elements(fg, btn_name)
        button_matches = [m for m in matches if m.get("type") == "ButtonControl"]
        if button_matches:
            target = button_matches[0]
            cx = target["bounds"]["center_x"]
            cy = target["bounds"]["center_y"]
            pyautogui.click(cx, cy)
            time.sleep(WAIT_POST_DISMISS)
            return {"recovery": "dismiss_dialog", "success": True,
                    "method": "click", "button": btn_name}

    return {"recovery": "dismiss_dialog", "success": False}


# ---------------------------------------------------------------------------
# Main healing pipeline
# ---------------------------------------------------------------------------

def heal_click(target_name: str, click_x: int, click_y: int,
               right: bool = False, double: bool = False,
               role: str = None) -> dict:
    """Attempt to heal a failed click action.

    Diagnoses the failure, applies recovery if possible, retries the click.

    Returns:
        {"healed": bool, "attempts": int, "diagnosis": dict,
         "result": dict (final click result or error)}
    """
    diagnosis = diagnose_click_failure(target_name, click_x, click_y, role=role)

    if not diagnosis["recoverable"]:
        return {
            "healed": False,
            "attempts": 0,
            "diagnosis": diagnosis,
            "suggestions": diagnosis.get("suggestions", []),
        }

    recovery_type = diagnosis["recovery"]

    for attempt in range(MAX_RETRIES):
        recovery_result = None

        if recovery_type == "relocate":
            recovery_result = recover_relocate(
                target_name, diagnosis["new_x"], diagnosis["new_y"],
                right=right, double=double,
            )
            if recovery_result["success"]:
                return {
                    "healed": True,
                    "attempts": attempt + 1,
                    "diagnosis": diagnosis,
                    "recovery": recovery_result,
                    "new_position": {"x": diagnosis["new_x"], "y": diagnosis["new_y"]},
                }

        elif recovery_type == "wait_enabled":
            recovery_result = recover_wait_enabled(target_name, role=role)
            if recovery_result["success"]:
                # Now click at the enabled element's position
                pyautogui.click(
                    recovery_result["x"], recovery_result["y"],
                    clicks=2 if double else 1,
                    button="right" if right else "left",
                )
                return {
                    "healed": True,
                    "attempts": attempt + 1,
                    "diagnosis": diagnosis,
                    "recovery": recovery_result,
                    "new_position": {"x": recovery_result["x"], "y": recovery_result["y"]},
                }

        elif recovery_type == "restore_window":
            recovery_result = recover_restore_window(diagnosis["expected_window"])
            if recovery_result["success"]:
                # Window restored — re-find element and click
                fg = auto.GetForegroundControl()
                matches = find_elements(fg, target_name)
                if role:
                    from nexus.digitus.element import _filter_by_role
                    matches = _filter_by_role(matches, role)
                if matches:
                    target = matches[0]
                    cx = target["bounds"]["center_x"]
                    cy = target["bounds"]["center_y"]
                    pyautogui.click(
                        cx, cy,
                        clicks=2 if double else 1,
                        button="right" if right else "left",
                    )
                    return {
                        "healed": True,
                        "attempts": attempt + 1,
                        "diagnosis": diagnosis,
                        "recovery": recovery_result,
                        "new_position": {"x": cx, "y": cy},
                    }

        elif recovery_type == "dismiss_dialog":
            recovery_result = recover_dismiss_dialog(diagnosis.get("dismiss_options", []))
            if recovery_result["success"]:
                # Dialog dismissed — re-find and click original target
                time.sleep(WAIT_POST_DISMISS)
                fg = auto.GetForegroundControl()
                matches = find_elements(fg, target_name)
                if role:
                    from nexus.digitus.element import _filter_by_role
                    matches = _filter_by_role(matches, role)
                if matches:
                    target = matches[0]
                    cx = target["bounds"]["center_x"]
                    cy = target["bounds"]["center_y"]
                    pyautogui.click(
                        cx, cy,
                        clicks=2 if double else 1,
                        button="right" if right else "left",
                    )
                    return {
                        "healed": True,
                        "attempts": attempt + 1,
                        "diagnosis": diagnosis,
                        "recovery": recovery_result,
                        "new_position": {"x": cx, "y": cy},
                    }

        # Re-diagnose for next attempt
        diagnosis = diagnose_click_failure(target_name, click_x, click_y, role=role)
        if not diagnosis["recoverable"]:
            break
        recovery_type = diagnosis["recovery"]

    # All retries exhausted
    return {
        "healed": False,
        "attempts": MAX_RETRIES,
        "diagnosis": diagnosis,
        "suggestions": _build_suggestions(diagnosis),
    }


def _build_suggestions(diagnosis: dict) -> list[str]:
    """Build actionable suggestions from a diagnosis."""
    suggestions = []
    ft = diagnosis.get("failure_type", "")

    if ft == "element_not_found":
        similar = diagnosis.get("suggestions", [])
        if similar:
            suggestions.append("Similar elements found: %s" % ", ".join(similar))
        suggestions.append("Try 'describe --focus interactive' to see available elements")
        suggestions.append("Try 'screenshot --mark' for visual element identification")

    elif ft == "dialog_blocking":
        dialog = diagnosis.get("dialog_name", "")
        dismiss = diagnosis.get("dismiss_options", [])
        if dismiss:
            suggestions.append("Try click-element '%s' to dismiss the dialog" % dismiss[0])
        else:
            suggestions.append("Dialog '%s' has no obvious dismiss button" % dialog)
            suggestions.append("Try pressing Escape or Alt+F4")

    elif ft == "element_disabled":
        suggestions.append("Element is disabled — may need a prerequisite action first")
        suggestions.append("Check form validation or required fields")

    elif ft == "window_changed":
        expected = diagnosis.get("expected_window", "")
        suggestions.append("Expected window '%s' is not in foreground" % expected)
        suggestions.append("Try 'windows' to list open windows")

    elif ft == "element_moved":
        suggestions.append("UI layout may have shifted — element was relocated successfully")

    return suggestions


# ---------------------------------------------------------------------------
# Web healing helpers
# ---------------------------------------------------------------------------

def heal_web_click(page, text: str, error_msg: str) -> dict:
    """Attempt to heal a failed web click.

    Tries:
      1. Wait for network idle (page might still be loading)
      2. Try alternative locator strategies (aria-label, role)
      3. Scroll element into view
    """
    strategies = []

    # Strategy 1: Wait for page to settle
    try:
        page.wait_for_load_state("networkidle", timeout=3000)
        locator = page.get_by_text(text, exact=False).first
        if locator.is_visible(timeout=1000):
            locator.click(timeout=3000)
            strategies.append("wait_for_load")
            return {
                "healed": True,
                "strategy": "wait_for_load",
                "clicked": text,
                "new_url": page.url,
            }
    except Exception:
        pass

    # Strategy 2: Try by role + name
    for role_name in ["button", "link", "tab", "menuitem"]:
        try:
            locator = page.get_by_role(role_name, name=text).first
            if locator.is_visible(timeout=500):
                locator.scroll_into_view_if_needed(timeout=1000)
                locator.click(timeout=3000)
                strategies.append("role_%s" % role_name)
                return {
                    "healed": True,
                    "strategy": "role_%s" % role_name,
                    "clicked": text,
                    "new_url": page.url,
                }
        except Exception:
            continue

    # Strategy 3: Try aria-label
    try:
        locator = page.locator('[aria-label*="%s" i]' % text.replace('"', '\\"')).first
        if locator.is_visible(timeout=500):
            locator.scroll_into_view_if_needed(timeout=1000)
            locator.click(timeout=3000)
            return {
                "healed": True,
                "strategy": "aria_label",
                "clicked": text,
                "new_url": page.url,
            }
    except Exception:
        pass

    return {
        "healed": False,
        "strategies_tried": strategies or ["wait_for_load", "role_search", "aria_label"],
        "error": error_msg,
        "suggestions": [
            "Try 'web-ax --focus interactive' to see available elements",
            "Try 'web-find \"%s\"' to locate the element" % text,
            "The page may need more time to load — try web-navigate first",
        ],
    }
