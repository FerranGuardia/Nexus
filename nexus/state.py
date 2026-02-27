"""Shared state between MCP server and control panel.

Communication happens through ~/.nexus/state.json:
- Panel writes: paused, hint, hint_ts
- MCP server writes: tool, action, status, step, error, app, ts, start_ts, log
- Both read the other's fields

Atomic writes via tmp+rename prevent partial reads.
In-memory cache avoids redundant disk I/O for rapid emit() calls.
"""

import json
import os
import time
from pathlib import Path

STATE_DIR = Path.home() / ".nexus"
STATE_FILE = STATE_DIR / "state.json"

# Maximum log entries kept
_MAX_LOG = 30

# In-memory state cache — avoids read+write disk I/O on every emit()
_mem_state = None       # cached state dict (None = not loaded yet)
_mem_dirty = False      # True if _mem_state has unflushed changes
_last_flush_ts = 0.0    # timestamp of last disk write
_EMIT_FLUSH_INTERVAL = 0.2  # seconds — max rate for emit() disk writes


def read_state():
    """Read the current shared state.

    Returns in-memory state if dirty (unflushed emit data), otherwise reads disk.
    This ensures callers always see the latest data including rate-limited emits.
    """
    if _mem_dirty and _mem_state is not None:
        return dict(_mem_state)
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        pass
    return {}


def _flush_to_disk(state):
    """Write state to disk atomically."""
    global _last_flush_ts
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False))
    tmp.rename(STATE_FILE)
    _last_flush_ts = time.time()


def write_state(**fields):
    """Merge fields into the shared state (atomic write).

    Only updates the specified fields, preserving others.
    Always updates 'ts' to current time. Always flushes to disk.
    Always reads from disk first to stay consistent with external writers (panel).
    """
    global _mem_state, _mem_dirty
    state = read_state()  # Always fresh from disk
    state.update(fields)
    state["ts"] = time.time()
    _mem_state = state  # Update cache for emit()
    _mem_dirty = False
    _flush_to_disk(state)


def emit(step):
    """Broadcast current sub-step to the panel. Lightweight — call freely.

    Uses in-memory state with rate-limited disk writes (max 1 per 200ms).
    This reduces 8-12 file I/O ops per do() to 2-3.
    Always flushes on first emit after start_action/write_state/clear.

    Examples:
        emit("Searching for 'Save' in element tree...")
        emit("Trying AXPress on [button] 'Save'...")
        emit("AX failed, clicking at (340, 220)...")
        emit("Waiting for 'dialog'... (3/10)")
    """
    global _mem_state, _mem_dirty
    try:
        if _mem_state is None:
            _mem_state = read_state()
        _mem_state["step"] = step
        _mem_state["ts"] = time.time()
        _mem_dirty = True

        # Rate-limit disk writes. Always flush if file doesn't exist yet.
        file_exists = STATE_FILE.exists()
        if not file_exists or time.time() - _last_flush_ts >= _EMIT_FLUSH_INTERVAL:
            _mem_dirty = False
            _flush_to_disk(_mem_state)
    except Exception:
        pass  # Never break the pipeline


def flush_if_dirty():
    """Flush any pending emit() state to disk. Call at action boundaries."""
    global _mem_dirty
    if _mem_dirty and _mem_state is not None:
        try:
            _mem_dirty = False
            _flush_to_disk(_mem_state)
        except Exception:
            pass


def start_action(tool, action, app=""):
    """Mark the start of an action — sets start_ts for elapsed time display.

    Always flushes to disk (action boundary).

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

    Always flushes to disk (action boundary).

    Args:
        status: "done" or "failed"
        error: Error message (for failures)
    """
    # Flush any pending emit() data first
    flush_if_dirty()

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
    global _mem_state, _mem_dirty
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
    _mem_state = default.copy()
    _mem_dirty = False
    _flush_to_disk(default)
