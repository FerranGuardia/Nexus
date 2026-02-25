"""Action bundles — common multi-step workflows as single intents.

Bundles are executable action sequences. Each bundle is a function that
orchestrates multiple do() steps to accomplish a common workflow.

Unlike skills (which are knowledge/guidance), bundles are code that runs.
Unlike chains (which are user-written), bundles are pre-built and tested.
"""

import re
import time
from nexus.act import native, input as raw_input
from nexus.state import emit


# ---------------------------------------------------------------------------
# Bundle registry
# ---------------------------------------------------------------------------

_BUNDLES = {}  # {pattern: (regex, handler)}


def _register(pattern, handler):
    """Register a bundle with a regex pattern."""
    _BUNDLES[pattern] = (re.compile(pattern, re.IGNORECASE), handler)


def match_bundle(action):
    """Try to match an action against registered bundles.

    Returns (handler, match) tuple or (None, None) if no match.
    """
    for _, (regex, handler) in _BUNDLES.items():
        m = regex.match(action.strip())
        if m:
            return handler, m
    return None, None


# ---------------------------------------------------------------------------
# Bundle implementations
# ---------------------------------------------------------------------------

def _bundle_save_as(match, pid=None):
    """Save file with a new name: "save as draft.md" or "save file as report.txt"."""
    filename = match.group("filename").strip()
    if not filename:
        return {"ok": False, "error": "No filename specified"}

    emit(f"Bundle: save as {filename}")

    # Step 1: Open Save As dialog
    raw_input.hotkey("command", "shift", "s")
    time.sleep(0.5)

    # Step 2: Type filename
    raw_input.type_text(filename)
    time.sleep(0.2)

    # Step 3: Press Enter to confirm
    raw_input.hotkey("return")

    return {"ok": True, "action": "bundle_save_as", "filename": filename}


def _bundle_find_replace(match, pid=None):
    """Find and replace text: "find and replace foo with bar"."""
    find_text = match.group("find").strip()
    replace_text = match.group("replace").strip()

    if not find_text:
        return {"ok": False, "error": "No search text specified"}

    emit(f"Bundle: find '{find_text}' → '{replace_text}'")

    # Step 1: Open Find & Replace
    raw_input.hotkey("command", "h")
    time.sleep(0.4)

    # Step 2: Type search text (field should be focused)
    raw_input.type_text(find_text)
    time.sleep(0.1)

    # Step 3: Tab to replace field, type replacement
    raw_input.hotkey("tab")
    time.sleep(0.1)
    raw_input.type_text(replace_text)

    return {"ok": True, "action": "bundle_find_replace",
            "find": find_text, "replace": replace_text}


def _bundle_new_document(match, pid=None):
    """Create a new document: "new document", "new file"."""
    emit("Bundle: new document")
    raw_input.hotkey("command", "n")
    return {"ok": True, "action": "bundle_new_document"}


def _bundle_print(match, pid=None):
    """Print current document: "print", "print document"."""
    emit("Bundle: print")
    raw_input.hotkey("command", "p")
    return {"ok": True, "action": "bundle_print"}


def _bundle_duplicate(match, pid=None):
    """Duplicate current file: "duplicate", "duplicate file"."""
    emit("Bundle: duplicate")
    raw_input.hotkey("command", "shift", "s")  # Some apps use Cmd+Shift+S for duplicate
    return {"ok": True, "action": "bundle_duplicate"}


def _bundle_zoom(match, pid=None):
    """Zoom in/out/reset: "zoom in", "zoom out", "zoom reset"."""
    direction = match.group("direction").lower().strip()
    emit(f"Bundle: zoom {direction}")

    if direction == "in":
        raw_input.hotkey("command", "=")  # Cmd++ (equals sign)
    elif direction == "out":
        raw_input.hotkey("command", "-")
    elif direction in ("reset", "actual", "100%", "100"):
        raw_input.hotkey("command", "0")
    else:
        return {"ok": False, "error": f"Unknown zoom direction: {direction}"}

    return {"ok": True, "action": "bundle_zoom", "direction": direction}


# ---------------------------------------------------------------------------
# Register all bundles
# ---------------------------------------------------------------------------

_register(
    r"save\s+(?:file\s+)?as\s+(?P<filename>.+)",
    _bundle_save_as,
)
_register(
    r"find\s+(?:and\s+)?replace\s+(?P<find>.+?)\s+with\s+(?P<replace>.+)",
    _bundle_find_replace,
)
_register(
    r"new\s+(?:document|file|window)$",
    _bundle_new_document,
)
_register(
    r"print(?:\s+(?:document|file|page))?$",
    _bundle_print,
)
_register(
    r"zoom\s+(?P<direction>in|out|reset|actual|100%?)",
    _bundle_zoom,
)
