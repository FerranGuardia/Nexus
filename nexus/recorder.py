"""Nexus Trajectory Recorder — passive logging for future Cortex training.

Appends one JSONL line per command execution to E:/NexusData/trajectories/.
Fire-and-forget: errors are silenced, never affects command execution.

Task lifecycle:
  nexus task start "description"  → creates task, tags all subsequent commands
  nexus task note "feedback"      → attaches human/agent feedback to current task
  nexus task end success|fail|partial  → closes the task with outcome
"""

import json
import os
import time

_NEXUS_DATA = os.environ.get("NEXUS_DATA_DIR", r"E:\NexusData")
_TRAJ_DIR = os.path.join(_NEXUS_DATA, "trajectories")
_SESSION_ID = "s_%s" % time.strftime("%Y%m%d_%H%M%S")

# Current task state (module-level, set by task_start/task_end)
_current_task = None  # {"id": "t_...", "name": "...", "started": timestamp}

# Task state file — persists across single-shot CLI invocations
_TASK_FILE = os.path.join(_NEXUS_DATA, ".current_task.json")

# Commands where full kwargs are useful (small results, action context matters)
_ACTION_COMMANDS = {
    "click", "move", "drag", "type", "key", "scroll",
    "click-element", "click-mark",
    "web-click", "web-navigate", "web-input", "web-pdf",
    "ps-run", "com-shell", "com-excel", "com-word", "com-outlook",
}

# Daemon builtins — skip recording
_SKIP_COMMANDS = {"ping", "quit", "commands", "task"}


def _load_task():
    """Load current task from disk (for single-shot CLI mode)."""
    global _current_task
    if _current_task is not None:
        return
    try:
        with open(_TASK_FILE, "r") as f:
            _current_task = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _current_task = None


def _save_task():
    """Persist current task to disk."""
    os.makedirs(_NEXUS_DATA, exist_ok=True)
    if _current_task:
        with open(_TASK_FILE, "w") as f:
            json.dump(_current_task, f)
    else:
        try:
            os.remove(_TASK_FILE)
        except FileNotFoundError:
            pass


def task_start(name: str) -> dict:
    """Start a new task. All subsequent commands get tagged with this task."""
    global _current_task
    task_id = "t_%s" % time.strftime("%Y%m%d_%H%M%S")
    _current_task = {"id": task_id, "name": name, "started": time.time()}
    _save_task()

    _write_entry({
        "type": "task_start",
        "task_id": task_id,
        "task_name": name,
    })

    return {
        "command": "task",
        "action": "start",
        "ok": True,
        "task_id": task_id,
        "task_name": name,
    }


def task_note(note: str) -> dict:
    """Attach feedback/notes to the current task."""
    _load_task()
    task_id = _current_task["id"] if _current_task else None

    _write_entry({
        "type": "task_note",
        "task_id": task_id,
        "note": note,
    })

    return {
        "command": "task",
        "action": "note",
        "ok": True,
        "task_id": task_id,
        "note": note,
    }


def task_end(outcome: str, notes: str = None) -> dict:
    """End the current task with an outcome: success, fail, or partial."""
    global _current_task
    _load_task()
    task_id = _current_task["id"] if _current_task else None
    task_name = _current_task["name"] if _current_task else None
    duration = time.time() - _current_task["started"] if _current_task else 0

    entry = {
        "type": "task_end",
        "task_id": task_id,
        "task_name": task_name,
        "outcome": outcome,
        "duration_sec": round(duration, 1),
    }
    if notes:
        entry["notes"] = notes

    _write_entry(entry)

    # Compact trajectory into memory (fire-and-forget)
    memory = None
    if task_id:
        try:
            from nexus.cortex.memory import compact_task
            memory = compact_task(task_id, task_name, outcome, round(duration, 1))
        except Exception:
            pass

    _current_task = None
    _save_task()

    result = {
        "command": "task",
        "action": "end",
        "ok": True,
        "task_id": task_id,
        "outcome": outcome,
        "duration_sec": round(duration, 1),
    }
    if memory:
        result["memory"] = memory
    return result


def task_status() -> dict:
    """Check if a task is currently active."""
    _load_task()
    if _current_task:
        return {
            "command": "task",
            "action": "status",
            "ok": True,
            "active": True,
            "task_id": _current_task["id"],
            "task_name": _current_task["name"],
            "running_sec": round(time.time() - _current_task["started"], 1),
        }
    return {"command": "task", "action": "status", "ok": True, "active": False}


def _extract_app_context(result: dict) -> str:
    """Pull app context from the result — URL for web, window title for UIA."""
    url = result.get("url", "")
    if url:
        clean = url.replace("file:///", "").replace("https://", "").replace("http://", "")
        return clean.split("?")[0][:120]

    window = result.get("window", {})
    if isinstance(window, dict) and window.get("title"):
        return window["title"][:120]

    return result.get("title", "")[:120] or "unknown"


def _summarize_result(cmd: str, result: dict) -> dict:
    """Compact summary of the result — enough to learn from, not the full blob."""
    summary = {"ok": result.get("ok", result.get("success", True))}

    if "error" in result:
        summary["error"] = str(result["error"])[:200]

    if "url" in result:
        summary["url"] = result["url"]

    if "elements" in result:
        elems = result["elements"]
        summary["element_count"] = len(elems) if isinstance(elems, list) else 0

    if "element_count" in result:
        summary["element_count"] = result["element_count"]

    if "title" in result:
        summary["title"] = result["title"][:100]

    return summary


def record(cmd: str, kwargs: dict, result: dict, duration_ms: int):
    """Append one trajectory entry. Fire-and-forget — never raises."""
    if cmd in _SKIP_COMMANDS:
        return

    try:
        _load_task()

        entry = {
            "ts": time.time(),
            "session": _SESSION_ID,
            "cmd": cmd,
            "kwargs": kwargs if cmd in _ACTION_COMMANDS else _compact_kwargs(kwargs),
            "duration_ms": duration_ms,
            "ok": result.get("ok", result.get("success", True)),
            "app_context": _extract_app_context(result),
            "result_summary": _summarize_result(cmd, result),
        }

        if _current_task:
            entry["task_id"] = _current_task["id"]

        _write_entry(entry)

    except Exception:
        pass  # never interfere with command execution


def _write_entry(entry: dict):
    """Append one JSONL line to today's trajectory file."""
    os.makedirs(_TRAJ_DIR, exist_ok=True)
    filename = "%s.jsonl" % time.strftime("%Y-%m-%d")
    path = os.path.join(_TRAJ_DIR, filename)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _compact_kwargs(kwargs: dict) -> dict:
    """For awareness commands, store only non-default kwargs to save space."""
    return {k: v for k, v in kwargs.items() if v is not None and v != 0 and v is not False}
