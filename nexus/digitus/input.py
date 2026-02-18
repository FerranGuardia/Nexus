"""Digitus Input — mouse, keyboard, and screenshot actions.

Every function takes explicit typed params and returns a dict.
"""

import os
import time

import pyautogui

SCREENSHOT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".tmp-screenshots",
)
DEFAULT_DOWNSCALE = (1920, 1080)


def screenshot(region: str | None = None, full: bool = False) -> dict:
    """Take a screenshot. Optionally capture a region (X,Y,W,H) or skip downscaling."""
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    filename = "nexus_%d.png" % int(time.time() * 1000)
    filepath = os.path.join(SCREENSHOT_DIR, filename)

    if region:
        parts = tuple(int(x) for x in region.split(","))
        img = pyautogui.screenshot(region=parts)
    else:
        img = pyautogui.screenshot()

    if not full:
        img = img.resize(DEFAULT_DOWNSCALE)

    img.save(filepath)
    return {"command": "screenshot", "path": filepath}


def click(x: int, y: int, right: bool = False, double: bool = False) -> dict:
    """Click at coordinates."""
    button = "right" if right else "left"
    clicks = 2 if double else 1
    pyautogui.click(x, y, clicks=clicks, button=button)
    return {"command": "click", "x": x, "y": y, "button": button, "double": double}


def move(x: int, y: int) -> dict:
    """Move cursor to coordinates."""
    pyautogui.moveTo(x, y)
    return {"command": "move", "x": x, "y": y}


def drag(start: str, end: str, duration: float = 0.5) -> dict:
    """Drag from start (X1,Y1) to end (X2,Y2)."""
    x1, y1 = (int(v) for v in start.split(","))
    x2, y2 = (int(v) for v in end.split(","))
    pyautogui.moveTo(x1, y1)
    pyautogui.drag(x2 - x1, y2 - y1, duration=duration)
    return {"command": "drag", "from": [x1, y1], "to": [x2, y2]}


def type_text(text: str) -> dict:
    """Type text. Uses key-by-key for ASCII, clipboard for unicode."""
    if text.isascii():
        pyautogui.typewrite(text, interval=0.02)
    else:
        pyautogui.write(text)
    return {"command": "type", "text": text}


def key(keyname: str) -> dict:
    """Press a key or combo (e.g. 'ctrl+s')."""
    keys = keyname.lower().split("+")
    if len(keys) == 1:
        pyautogui.press(keys[0])
    else:
        pyautogui.hotkey(*keys)
    return {"command": "key", "keys": keyname}


def scroll(amount: int) -> dict:
    """Scroll. Positive=up, negative=down."""
    pyautogui.scroll(amount)
    direction = "up" if amount > 0 else "down"
    return {"command": "scroll", "amount": amount, "direction": direction}


def info() -> dict:
    """Screen size and cursor position."""
    size = pyautogui.size()
    pos = pyautogui.position()
    return {
        "command": "info",
        "screen": {"width": size.width, "height": size.height},
        "cursor": {"x": pos.x, "y": pos.y},
    }
