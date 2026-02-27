"""CGEventTap — capture raw user input (mouse clicks, key presses, scrolls).

Runs a listen-only CGEventTap on a background thread to record what the user
does without modifying any events. Each captured event is enriched with:
- AX element at the click position (role + label)
- Window bounds → relative coordinates (position-independent)
- Frontmost app context (PID + name)

Follows the same background-thread + CFRunLoop pattern as observe.py.

Usage:
    start_tap()   — begin capturing input events
    stop_tap()    — stop and return all captured events
    drain_events() — atomically drain buffer without stopping
    is_tapping()  — check if tap is active
"""

import json
import threading
import time
from collections import deque

from Quartz import (
    CGEventTapCreate,
    CGEventTapEnable,
    CGEventGetLocation,
    CGEventGetType,
    CGEventGetFlags,
    CGEventGetIntegerValueField,
    CFMachPortCreateRunLoopSource,
    CFRunLoopAddSource,
    CFRunLoopGetCurrent,
    CFRunLoopRunInMode,
    CFRunLoopStop,
    CGWindowListCopyWindowInfo,
    kCGSessionEventTap,
    kCGHeadInsertEventTap,
    kCGEventTapOptionListenOnly,
    kCGEventLeftMouseDown,
    kCGEventRightMouseDown,
    kCGEventOtherMouseDown,
    kCGEventKeyDown,
    kCGEventScrollWheel,
    kCGWindowListOptionOnScreenOnly,
    kCGWindowListExcludeDesktopElements,
    kCGNullWindowID,
    kCGKeyboardEventKeycode,
    kCGScrollWheelEventDeltaAxis1,
    kCFRunLoopDefaultMode,
    kCGEventFlagMaskShift,
    kCGEventFlagMaskControl,
    kCGEventFlagMaskAlternate,
    kCGEventFlagMaskCommand,
)
from AppKit import NSWorkspace


# ---------------------------------------------------------------------------
# Key code → human-readable mapping (macOS virtual key codes)
# ---------------------------------------------------------------------------

_KEY_NAMES = {
    0: "a", 1: "s", 2: "d", 3: "f", 4: "h", 5: "g", 6: "z", 7: "x",
    8: "c", 9: "v", 11: "b", 12: "q", 13: "w", 14: "e", 15: "r",
    16: "y", 17: "t", 18: "1", 19: "2", 20: "3", 21: "4", 22: "6",
    23: "5", 24: "=", 25: "9", 26: "7", 27: "-", 28: "8", 29: "0",
    30: "]", 31: "o", 32: "u", 33: "[", 34: "i", 35: "p",
    36: "return", 37: "l", 38: "j", 39: "'", 40: "k", 41: ";",
    42: "\\", 43: ",", 44: "/", 45: "n", 46: "m", 47: ".",
    48: "tab", 49: "space", 50: "`", 51: "delete", 53: "escape",
    55: "command", 56: "shift", 57: "capslock", 58: "option",
    59: "control", 60: "rightshift", 61: "rightoption",
    62: "rightcontrol", 63: "fn",
    76: "enter", 96: "f5", 97: "f6", 98: "f7", 99: "f3",
    100: "f8", 101: "f9", 103: "f11", 105: "f13",
    107: "f14", 109: "f10", 111: "f12", 113: "f15",
    115: "home", 116: "pageup", 117: "forwarddelete",
    118: "f4", 119: "end", 120: "f2", 121: "pagedown", 122: "f1",
    123: "left", 124: "right", 125: "down", 126: "up",
}

# Modifier-only key codes — skip these as standalone events
_MODIFIER_KEYCODES = {55, 56, 57, 58, 59, 60, 61, 62, 63}


# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_MAX_EVENTS = 5000

_event_buffer = deque(maxlen=_MAX_EVENTS)
_lock = threading.Lock()

_thread = None
_runloop = None
_runloop_ready = None
_stop_flag = threading.Event()
_recording_start = None  # time.time() when recording started

# Cached frontmost app info (refreshed on each event)
_front_app_cache = {"pid": None, "name": None, "ts": 0}
_FRONT_APP_TTL = 0.5  # refresh every 500ms


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_front_app():
    """Get frontmost app PID and name (cached with short TTL)."""
    now = time.time()
    if now - _front_app_cache["ts"] < _FRONT_APP_TTL and _front_app_cache["pid"]:
        return _front_app_cache["pid"], _front_app_cache["name"]

    try:
        ws = NSWorkspace.sharedWorkspace()
        front = ws.frontmostApplication()
        if front:
            pid = front.processIdentifier()
            name = str(front.localizedName() or "")
            _front_app_cache["pid"] = pid
            _front_app_cache["name"] = name
            _front_app_cache["ts"] = now
            return pid, name
    except Exception:
        pass
    return _front_app_cache["pid"], _front_app_cache["name"]


def _get_modifiers(flags):
    """Extract modifier state from CGEvent flags."""
    return {
        "cmd": bool(flags & kCGEventFlagMaskCommand),
        "shift": bool(flags & kCGEventFlagMaskShift),
        "ctrl": bool(flags & kCGEventFlagMaskControl),
        "opt": bool(flags & kCGEventFlagMaskAlternate),
    }


def _find_window_at(x, y, pid=None):
    """Find the window containing point (x, y). Returns bounds dict or None.

    Returns {"x": int, "y": int, "w": int, "h": int} for the matching window.
    """
    try:
        windows = CGWindowListCopyWindowInfo(
            kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements,
            kCGNullWindowID,
        )
        if not windows:
            return None

        for w in windows:
            if pid and w.get("kCGWindowOwnerPID") != pid:
                continue
            bounds = w.get("kCGWindowBounds")
            if not bounds:
                continue
            wx = int(bounds.get("X", 0))
            wy = int(bounds.get("Y", 0))
            ww = int(bounds.get("Width", 0))
            wh = int(bounds.get("Height", 0))
            if ww <= 0 or wh <= 0:
                continue
            if wx <= x <= wx + ww and wy <= y <= wy + wh:
                return {"x": wx, "y": wy, "w": ww, "h": wh}
    except Exception:
        pass
    return None


def _hit_test_ax(x, y, pid=None):
    """AX hit-test: find element at screen position. Returns (role, label) or (None, None)."""
    try:
        from nexus.sense.access import element_at_position
        el = element_at_position(x, y, pid=pid)
        if el:
            return el.get("_ax_role", ""), el.get("label", "")
    except Exception:
        pass
    return None, None


def _key_char(key_code, modifiers):
    """Convert key code + modifiers to human-readable string like 'cmd+s'."""
    name = _KEY_NAMES.get(key_code, f"key{key_code}")
    parts = []
    if modifiers.get("cmd"):
        parts.append("cmd")
    if modifiers.get("ctrl"):
        parts.append("ctrl")
    if modifiers.get("opt"):
        parts.append("opt")
    if modifiers.get("shift"):
        parts.append("shift")
    parts.append(name)
    return "+".join(parts)


# ---------------------------------------------------------------------------
# CGEventTap callback
# ---------------------------------------------------------------------------

def _on_event(proxy, etype, event, refcon):
    """CGEventTap callback — runs on the tap thread.

    Extracts event data, enriches with AX hit-test and window bounds,
    appends to the shared buffer. Returns event unchanged (listen-only).
    """
    if _recording_start is None:
        return event

    now = time.time()
    ts_offset = (now - _recording_start) * 1000.0  # ms

    loc = CGEventGetLocation(event)
    x, y = int(loc.x), int(loc.y)
    flags = CGEventGetFlags(event)
    modifiers = _get_modifiers(flags)
    pid, app_name = _get_front_app()

    ev = {
        "ts_offset_ms": round(ts_offset, 1),
        "x": x, "y": y,
        "modifiers": modifiers,
        "pid": pid,
        "app_name": app_name,
    }

    etype_int = CGEventGetType(event)

    if etype_int in (kCGEventLeftMouseDown, kCGEventRightMouseDown, kCGEventOtherMouseDown):
        # Mouse click
        if etype_int == kCGEventLeftMouseDown:
            ev["button"] = "left"
        elif etype_int == kCGEventRightMouseDown:
            ev["button"] = "right"
        else:
            ev["button"] = "middle"
        ev["event_type"] = "click"

        # AX hit-test
        ax_role, ax_label = _hit_test_ax(x, y, pid=pid)
        if ax_role:
            ev["ax_role"] = ax_role
        if ax_label:
            ev["ax_label"] = ax_label

        # Window bounds → relative coordinates
        win = _find_window_at(x, y, pid=pid)
        if win:
            ev["window_x"] = win["x"]
            ev["window_y"] = win["y"]
            ev["window_w"] = win["w"]
            ev["window_h"] = win["h"]
            if win["w"] > 0 and win["h"] > 0:
                ev["rel_x"] = round((x - win["x"]) / win["w"], 4)
                ev["rel_y"] = round((y - win["y"]) / win["h"], 4)

    elif etype_int == kCGEventKeyDown:
        key_code = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
        # Skip modifier-only key presses
        if key_code in _MODIFIER_KEYCODES:
            return event
        ev["event_type"] = "key"
        ev["key_code"] = int(key_code)
        ev["key_char"] = _key_char(int(key_code), modifiers)

    elif etype_int == kCGEventScrollWheel:
        delta = CGEventGetIntegerValueField(event, kCGScrollWheelEventDeltaAxis1)
        ev["event_type"] = "scroll"
        ev["button"] = "up" if delta > 0 else "down"

    else:
        # Unknown event type — skip
        return event

    with _lock:
        _event_buffer.append(ev)

    return event


# ---------------------------------------------------------------------------
# Background thread
# ---------------------------------------------------------------------------

def _tap_loop():
    """Background thread: runs CGEventTap on a CFRunLoop.

    Creates a listen-only event tap for mouse clicks, key presses, and scrolls.
    Uses CFRunLoopRunInMode in a loop (same pattern as observe.py).
    """
    global _runloop

    # Event mask: left click, right click, middle click, key down, scroll
    mask = (
        (1 << kCGEventLeftMouseDown) |
        (1 << kCGEventRightMouseDown) |
        (1 << kCGEventOtherMouseDown) |
        (1 << kCGEventKeyDown) |
        (1 << kCGEventScrollWheel)
    )

    tap = CGEventTapCreate(
        kCGSessionEventTap,
        kCGHeadInsertEventTap,
        kCGEventTapOptionListenOnly,
        mask,
        _on_event,
        None,
    )

    if tap is None:
        _runloop_ready.set()
        return

    source = CFMachPortCreateRunLoopSource(None, tap, 0)
    _runloop = CFRunLoopGetCurrent()
    CFRunLoopAddSource(_runloop, source, kCFRunLoopDefaultMode)
    CGEventTapEnable(tap, True)

    _runloop_ready.set()

    while not _stop_flag.is_set():
        CFRunLoopRunInMode(kCFRunLoopDefaultMode, 1.0, False)

    # Cleanup
    CGEventTapEnable(tap, False)
    _runloop = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_tap():
    """Start capturing input events on a background thread.

    Returns True if tap started successfully, False if it was already running
    or failed to create.
    """
    global _thread, _runloop_ready, _recording_start

    with _lock:
        if _thread is not None and _thread.is_alive():
            return False
        _stop_flag.clear()
        _event_buffer.clear()
        _recording_start = time.time()
        _runloop_ready = threading.Event()
        _thread = threading.Thread(target=_tap_loop, daemon=True, name="nexus-via-tap")
        _thread.start()

    _runloop_ready.wait(timeout=3.0)
    return _runloop is not None


def stop_tap():
    """Stop capturing and return all buffered events.

    Returns list of event dicts, ordered by ts_offset_ms.
    """
    global _thread, _recording_start

    _stop_flag.set()

    if _thread is not None:
        if _runloop:
            try:
                CFRunLoopStop(_runloop)
            except Exception:
                pass
        _thread.join(timeout=3.0)
        _thread = None

    _recording_start = None

    with _lock:
        events = list(_event_buffer)
        _event_buffer.clear()
    return events


def drain_events():
    """Atomically drain all buffered events without stopping the tap."""
    with _lock:
        events = list(_event_buffer)
        _event_buffer.clear()
    return events


def is_tapping():
    """Check if the event tap is currently active."""
    return _thread is not None and _thread.is_alive() and _recording_start is not None


def shutdown():
    """Clean shutdown — stop tap if running."""
    if is_tapping():
        stop_tap()
