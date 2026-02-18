"""Cortex Memory — trajectory compaction and recall.

On task end, reads the task's trajectory entries from JSONL and compacts them
into a structured memory entry. Memories are stored in E:/NexusData/knowledge/
and can be queried by app, task name, or tags.

This is the Level 2 Cortex foundation: Claude's past actions become queryable
knowledge, reducing repeated exploration of the same apps/workflows.

Zero LLM calls. All local string processing.
"""

import json
import os
import time
from collections import Counter
from datetime import datetime, timedelta

_NEXUS_DATA = os.environ.get("NEXUS_DATA_DIR", r"E:\NexusData")
_TRAJ_DIR = os.path.join(_NEXUS_DATA, "trajectories")
_KNOWLEDGE_DIR = os.path.join(_NEXUS_DATA, "knowledge")
_MEMORIES_FILE = os.path.join(_KNOWLEDGE_DIR, "memories.jsonl")

# Commands that represent meaningful action steps (not meta/lifecycle)
_STEP_COMMANDS = {
    "describe", "windows", "find", "focused",
    "web-describe", "web-text", "web-find", "web-links", "web-tabs",
    "web-ax", "web-measure", "web-markdown", "web-research", "web-capture-api",
    "ocr-region", "ocr-screen",
    "screenshot", "click", "move", "drag", "type", "key", "scroll",
    "click-element", "click-mark",
    "web-click", "web-navigate", "web-input", "web-pdf",
    "ps-run", "com-shell", "com-excel", "com-word", "com-outlook",
    "electron-detect", "electron-connect", "electron-targets",
    "info",
}

# Keywords for auto-tagging
_TAG_RULES = {
    "web": {"web-describe", "web-text", "web-find", "web-links", "web-tabs",
            "web-ax", "web-measure", "web-markdown", "web-click", "web-navigate",
            "web-input", "web-pdf", "web-research", "web-capture-api"},
    "interaction": {"click", "type", "key", "scroll", "drag", "click-element",
                    "click-mark", "web-click", "web-input"},
    "observation": {"describe", "windows", "find", "focused", "web-describe",
                    "web-text", "web-ax", "screenshot", "ocr-region", "ocr-screen"},
    "office": {"com-excel", "com-word", "com-outlook"},
    "system": {"ps-run", "com-shell"},
    "electron": {"electron-detect", "electron-connect", "electron-targets"},
}


def compact_task(task_id: str, task_name: str, outcome: str, duration_sec: float) -> dict:
    """Read task entries from trajectory JSONL, compact into a memory, store it.

    Returns the memory entry dict.
    """
    entries = _read_task_entries(task_id)
    steps = [e for e in entries if e.get("cmd") in _STEP_COMMANDS]

    memory = {
        "task_id": task_id,
        "task_name": task_name,
        "outcome": outcome,
        "duration_sec": duration_sec,
        "completed_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "step_count": len(steps),
        "steps_summary": _build_steps_summary(steps),
        "key_actions": _extract_key_actions(steps),
        "apps_used": _extract_apps_used(steps),
        "app_context": _primary_app_context(steps),
        "tags": _auto_tag(task_name, steps),
    }

    _write_memory(memory)
    return memory


def _read_task_entries(task_id: str) -> list:
    """Scan today's and yesterday's trajectory JSONL for entries matching task_id."""
    entries = []
    today = datetime.now()
    dates = [today.strftime("%Y-%m-%d"), (today - timedelta(days=1)).strftime("%Y-%m-%d")]

    for date_str in dates:
        path = os.path.join(_TRAJ_DIR, "%s.jsonl" % date_str)
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("task_id") == task_id:
                        entries.append(entry)
        except OSError:
            continue

    return entries


def _build_steps_summary(entries: list) -> list:
    """Convert trajectory entries into compact step descriptions.

    Format: "cmd_name key_arg" — e.g. "web-click 'Projects'", "describe", "type 'hello'"
    """
    steps = []
    for entry in entries:
        cmd = entry.get("cmd", "")
        kwargs = entry.get("kwargs", {})
        desc = _step_description(cmd, kwargs)
        steps.append(desc)
    return steps


def _step_description(cmd: str, kwargs: dict) -> str:
    """Build a human-readable one-liner for a command execution."""
    # Action commands with a primary positional arg
    primary_arg_keys = {
        "click": lambda k: "%s,%s" % (k.get("x", "?"), k.get("y", "?")),
        "move": lambda k: "%s,%s" % (k.get("x", "?"), k.get("y", "?")),
        "type": lambda k: "'%s'" % str(k.get("text", ""))[:40],
        "key": lambda k: k.get("keyname", ""),
        "scroll": lambda k: str(k.get("amount", "")),
        "click-element": lambda k: "'%s'" % str(k.get("name", ""))[:40],
        "click-mark": lambda k: str(k.get("mark_id", "")),
        "web-click": lambda k: "'%s'" % str(k.get("text", ""))[:40],
        "web-navigate": lambda k: str(k.get("url", ""))[:60],
        "web-input": lambda k: "%s='%s'" % (k.get("selector", "?"), str(k.get("value", ""))[:30]),
        "find": lambda k: "'%s'" % str(k.get("query", ""))[:40],
        "web-find": lambda k: "'%s'" % str(k.get("query", ""))[:40],
        "ps-run": lambda k: str(k.get("script", ""))[:50],
        "com-shell": lambda k: k.get("path", ""),
    }

    formatter = primary_arg_keys.get(cmd)
    if formatter:
        arg_str = formatter(kwargs)
        return "%s %s" % (cmd, arg_str) if arg_str else cmd

    # Awareness commands — just the command name, maybe with focus
    focus = kwargs.get("focus")
    if focus:
        return "%s --focus %s" % (cmd, focus)

    return cmd


def _extract_key_actions(entries: list) -> list:
    """Unique command names in execution order."""
    seen = set()
    actions = []
    for entry in entries:
        cmd = entry.get("cmd", "")
        if cmd and cmd not in seen:
            seen.add(cmd)
            actions.append(cmd)
    return actions


def _extract_apps_used(entries: list) -> list:
    """Unique app_context values across all entries."""
    seen = set()
    apps = []
    for entry in entries:
        ctx = entry.get("app_context", "")
        if ctx and ctx != "unknown" and ctx not in seen:
            seen.add(ctx)
            apps.append(ctx)
    return apps


def _primary_app_context(entries: list) -> str:
    """Most frequently used app context across entries."""
    if not entries:
        return "unknown"
    counts = Counter(e.get("app_context", "unknown") for e in entries)
    # Remove "unknown" if there are real contexts
    if len(counts) > 1:
        counts.pop("unknown", None)
    return counts.most_common(1)[0][0]


def _auto_tag(task_name: str, entries: list) -> list:
    """Generate tags from task name keywords and command types used."""
    tags = set()
    cmds_used = {e.get("cmd", "") for e in entries}

    # Tag based on commands used
    for tag, cmd_set in _TAG_RULES.items():
        if cmds_used & cmd_set:
            tags.add(tag)

    # Tag based on task name keywords
    name_lower = task_name.lower()
    keyword_tags = {
        "navigation": ["navigate", "go to", "open", "visit"],
        "search": ["search", "find", "look for", "locate"],
        "setup": ["setup", "configure", "install", "settings"],
        "debug": ["debug", "fix", "error", "bug", "troubleshoot"],
        "data": ["data", "export", "import", "download", "upload"],
        "email": ["email", "mail", "send", "inbox"],
    }
    for tag, keywords in keyword_tags.items():
        if any(kw in name_lower for kw in keywords):
            tags.add(tag)

    return sorted(tags)


def _write_memory(memory: dict):
    """Append one JSONL line to memories file. Fire-and-forget."""
    try:
        os.makedirs(_KNOWLEDGE_DIR, exist_ok=True)
        with open(_MEMORIES_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(memory, ensure_ascii=False) + "\n")
    except Exception:
        pass


def recall(query: str = None, app: str = None, tag: str = None, limit: int = 10) -> dict:
    """Search memories by substring in task_name, app_context, or tag.

    Multiple filters are AND'd. Case-insensitive. Newest first.
    """
    if not os.path.exists(_MEMORIES_FILE):
        return {"command": "recall", "ok": True, "memories": [], "count": 0}

    # Read all memories (reverse for newest-first)
    all_memories = []
    try:
        with open(_MEMORIES_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    all_memories.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return {"command": "recall", "ok": True, "memories": [], "count": 0}

    all_memories.reverse()

    # Filter
    matches = []
    query_lower = query.lower() if query else None
    app_lower = app.lower() if app else None
    tag_lower = tag.lower() if tag else None

    for mem in all_memories:
        if query_lower and query_lower not in mem.get("task_name", "").lower():
            continue
        if app_lower and app_lower not in mem.get("app_context", "").lower():
            continue
        if tag_lower and tag_lower not in [t.lower() for t in mem.get("tags", [])]:
            continue
        matches.append(mem)
        if len(matches) >= limit:
            break

    return {"command": "recall", "ok": True, "memories": matches, "count": len(matches)}


def recall_stats() -> dict:
    """Aggregate stats over all memories."""
    if not os.path.exists(_MEMORIES_FILE):
        return {"command": "recall", "ok": True, "total": 0}

    memories = []
    try:
        with open(_MEMORIES_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        memories.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except OSError:
        return {"command": "recall", "ok": True, "total": 0}

    total = len(memories)
    if total == 0:
        return {"command": "recall", "ok": True, "total": 0}

    outcomes = Counter(m.get("outcome", "unknown") for m in memories)
    success_rate = round(outcomes.get("success", 0) / total * 100, 1)

    app_counts = Counter(m.get("app_context", "unknown") for m in memories)
    tag_counts = Counter()
    for m in memories:
        for t in m.get("tags", []):
            tag_counts[t] += 1

    return {
        "command": "recall",
        "ok": True,
        "total": total,
        "success_rate_pct": success_rate,
        "outcomes": dict(outcomes),
        "top_apps": dict(app_counts.most_common(5)),
        "top_tags": dict(tag_counts.most_common(10)),
        "avg_duration_sec": round(sum(m.get("duration_sec", 0) for m in memories) / total, 1),
        "avg_steps": round(sum(m.get("step_count", 0) for m in memories) / total, 1),
    }
