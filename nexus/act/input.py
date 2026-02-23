"""Low-level mouse/keyboard input via pyautogui.

Fallback layer when accessibility actions aren't available.
"""

import pyautogui

# Safety: don't let pyautogui throw on edge-of-screen moves
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05  # Small pause between actions


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
    """Type text using keyboard."""
    pyautogui.write(text, interval=interval)
    return {"ok": True, "action": "type", "text": text}


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
