"""Shared state between MCP server and control panel.

Communication happens through ~/.nexus/state.json:
- Panel writes: paused, hint, hint_ts
- MCP server writes: tool, action, status, step, error, app, ts, start_ts, log
- Both read the other's fields

Atomic writes via tmp+rename prevent partial reads.
"""

import json
import os
import time
from pathlib import Path

STATE_DIR = Path.home() / ".nexus"
STATE_FILE = STATE_DIR / "state.json"

# Maximum log entries kept
_MAX_LOG = 30


def read_state():
    """Read the current shared state. Returns empty dict if no state file."""
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        pass
    return {}


def write_state(**fields):
    """Merge fields into the shared state (atomic write).

    Only updates the specified fields, preserving others.
    Always updates 'ts' to current time.
    """
    state = read_state()
    state.update(fields)
    state["ts"] = time.time()

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    # Atomic write: tmp file + rename
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False))
    tmp.rename(STATE_FILE)


def emit(step):
    """Broadcast current sub-step to the panel. Lightweight — call freely.

    This is the main instrumentation hook. Sprinkle emit() calls at key
    decision points in the pipeline so the panel shows where Nexus is.

    Examples:
        emit("Searching for 'Save' in element tree...")
        emit("Trying AXPress on [button] 'Save'...")
        emit("AX failed, clicking at (340, 220)...")
        emit("Waiting for 'dialog'... (3/10)")
    """
    try:
        state = read_state()
        state["step"] = step
        state["ts"] = time.time()
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False))
        tmp.rename(STATE_FILE)
    except Exception:
        pass  # Never break the pipeline


def start_action(tool, action, app=""):
    """Mark the start of an action — sets start_ts for elapsed time display.

    Args:
        tool: "see", "do", or "memory"
        action: The action string (e.g. "click Save", "query=search")
        app: Target app name (optional)
    """
    write_state(
        tool=tool,
        action=action,
        app=app,
        status="running",
        step="",
        error="",
        start_ts=time.time(),
    )


def end_action(status, error=""):
    """Mark the end of an action and append to the log.

    Args:
        status: "done" or "failed"
        error: Error message (for failures)
    """
    state = read_state()
    start_ts = state.get("start_ts", time.time())
    elapsed = round(time.time() - start_ts, 2)
    action = state.get("action", "")

    # Append to log
    log = state.get("log", [])
    log.append({
        "action": action,
        "tool": state.get("tool", ""),
        "status": status,
        "elapsed": elapsed,
        "error": error[:200] if error else "",
        "ts": time.time(),
    })
    # Cap log size
    if len(log) > _MAX_LOG:
        log = log[-_MAX_LOG:]

    write_state(status=status, error=error, step="", log=log)


def read_and_clear_hint():
    """Read the user's hint and clear it. Returns None if no hint."""
    state = read_state()
    hint = state.get("hint", "").strip()
    if not hint:
        return None

    # Clear the hint
    write_state(hint="", hint_ts=0)
    return hint


def clear_state():
    """Reset all state to defaults."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    default = {
        "paused": False,
        "hint": "",
        "hint_ts": 0,
        "tool": "",
        "action": "",
        "status": "idle",
        "step": "",
        "error": "",
        "app": "",
        "start_ts": 0,
        "ts": time.time(),
        "log": [],
    }
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(default, ensure_ascii=False))
    tmp.rename(STATE_FILE)
