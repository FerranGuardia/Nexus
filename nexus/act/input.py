"""Low-level mouse/keyboard input via pyautogui.

Fallback layer when accessibility actions aren't available.
"""

import subprocess
import time

import pyautogui

# Safety: don't let pyautogui throw on edge-of-screen moves
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05  # Small pause between actions

# Strings longer than this use clipboard paste instead of char-by-char.
# Prevents rapid beeping when field isn't focused, and is faster for
# long strings like URLs, server addresses, email addresses.
_PASTE_THRESHOLD = 8


def click(x, y, button="left", clicks=1):
    """Click at screen coordinates."""
    pyautogui.click(x, y, button=button, clicks=clicks)
    return {"ok": True, "action": "click", "x": x, "y": y}


def double_click(x, y):
    """Double-click at screen coordinates."""
    pyautogui.doubleClick(x, y)
    return {"ok": True, "action": "double_click", "x": x, "y": y}


def triple_click(x, y):
    """Triple-click at screen coordinates (select line/paragraph)."""
    pyautogui.click(x, y, clicks=3)
    return {"ok": True, "action": "triple_click", "x": x, "y": y}


def right_click(x, y):
    """Right-click at screen coordinates."""
    pyautogui.rightClick(x, y)
    return {"ok": True, "action": "right_click", "x": x, "y": y}


def type_text(text, interval=0.02):
    """Type text using keyboard.

    Short strings (<= 8 chars): character-by-character via pyautogui.
    Long strings (> 8 chars): clipboard paste via cmd+v.
    This prevents rapid beeping if the field isn't focused, and is
    faster for URLs, server addresses, etc.
    """
    if len(text) > _PASTE_THRESHOLD:
        return paste_text(text)
    pyautogui.write(text, interval=interval)
    return {"ok": True, "action": "type", "text": text}


def paste_text(text):
    """Type text atomically via clipboard paste (cmd+v).

    One keypress instead of N — if field isn't focused, one beep
    instead of 26. Saves and restores the original clipboard.
    """
    # Save current clipboard
    old_clip = None
    try:
        result = subprocess.run(
            ["pbpaste"], capture_output=True, timeout=2,
        )
        old_clip = result.stdout  # bytes — preserves any encoding
    except Exception:
        pass

    # Set clipboard to our text
    try:
        subprocess.run(
            ["pbcopy"], input=text.encode("utf-8"), timeout=2,
        )
    except Exception:
        # Clipboard failed — fall back to char-by-char
        pyautogui.write(text, interval=0.02)
        return {"ok": True, "action": "type", "text": text}

    # Paste
    pyautogui.hotkey("command", "v")

    # Pause for paste to register before restoring clipboard.
    # 0.3s needed for async fields (Mail.app IMAP/SMTP server addresses).
    time.sleep(0.3)
    if old_clip is not None:
        try:
            subprocess.run(
                ["pbcopy"], input=old_clip, timeout=2,
            )
        except Exception:
            pass

    return {"ok": True, "action": "paste", "text": text}


def hotkey(*keys):
    """Press a keyboard shortcut (e.g. hotkey('command', 's'))."""
    pyautogui.hotkey(*keys)
    return {"ok": True, "action": "hotkey", "keys": list(keys)}


def press(key):
    """Press a single key."""
    pyautogui.press(key)
    return {"ok": True, "action": "press", "key": key}


def scroll(clicks, x=None, y=None):
    """Scroll. Positive = up, negative = down."""
    if x is not None and y is not None:
        pyautogui.scroll(clicks, x, y)
    else:
        pyautogui.scroll(clicks)
    return {"ok": True, "action": "scroll", "clicks": clicks}


def move_to(x, y):
    """Move mouse to coordinates."""
    pyautogui.moveTo(x, y)
    return {"ok": True, "action": "move", "x": x, "y": y}


def drag(x1, y1, x2, y2, duration=0.5):
    """Drag from one point to another using absolute coordinates."""
    pyautogui.moveTo(x1, y1)
    pyautogui.mouseDown()
    pyautogui.moveTo(x2, y2, duration=duration)
    pyautogui.mouseUp()
    return {"ok": True, "action": "drag", "from": [x1, y1], "to": [x2, y2]}


def hover(x, y):
    """Move mouse to coordinates without clicking."""
    pyautogui.moveTo(x, y)
    return {"ok": True, "action": "hover", "x": x, "y": y}


def modifier_click(x, y, modifiers):
    """Click while holding modifier keys (shift, command, option, control).

    Args:
        x, y: Screen coordinates.
        modifiers: List of modifier names (e.g. ["shift"], ["command", "shift"]).
    """
    for mod in modifiers:
        pyautogui.keyDown(mod)
    pyautogui.click(x, y)
    for mod in reversed(modifiers):
        pyautogui.keyUp(mod)
    return {"ok": True, "action": "modifier_click", "x": x, "y": y, "modifiers": modifiers}


def mouse_position():
    """Get current mouse position."""
    pos = pyautogui.position()
    return {"x": pos[0], "y": pos[1]}


def screen_size():
    """Get screen dimensions."""
    size = pyautogui.size()
    return {"width": size[0], "height": size[1]}
