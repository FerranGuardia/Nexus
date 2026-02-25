"""Persistent key-value memory — the `memory` tool.

Simple key-value store backed by SQLite (via db.py).
The AI remembers what it learns about the user, the machine,
and patterns it discovers.
"""

import json
from datetime import datetime


def memory(op, key=None, value=None):
    """Persistent memory operations.

    Args:
        op: "get", "set", "delete", "list", "clear"
        key: Memory key (required for get/set/delete)
        value: Value to store (required for set)

    Returns:
        dict with result.
    """
    op = op.lower().strip()

    if op == "set":
        if not key:
            return {"ok": False, "error": "Key required for set"}
        if value is None:
            return {"ok": False, "error": "Value required for set"}
        _set(key, value)
        return {"ok": True, "action": "set", "key": key}

    if op == "get":
        if not key:
            return {"ok": False, "error": "Key required for get"}
        val = _get(key)
        if val is None:
            return {"ok": False, "error": f'Key "{key}" not found'}
        return {"ok": True, "key": key, "value": val}

    if op == "delete":
        if not key:
            return {"ok": False, "error": "Key required for delete"}
        deleted = _delete(key)
        if deleted:
            return {"ok": True, "action": "delete", "key": key}
        return {"ok": False, "error": f'Key "{key}" not found'}

    if op == "list":
        from nexus.mind.db import mem_list
        keys = mem_list()
        if not keys:
            return {"ok": True, "keys": [], "count": 0}
        return {"ok": True, "keys": keys, "count": len(keys)}

    if op == "clear":
        from nexus.mind.db import mem_clear
        mem_clear()
        return {"ok": True, "action": "clear"}

    return {"ok": False, "error": f'Unknown op: "{op}". Use: get, set, delete, list, clear'}


def _get(key):
    """Get a value by key."""
    from nexus.mind.db import mem_get
    entry = mem_get(key)
    if entry is None:
        return None
    # Values are stored as JSON strings in SQLite
    try:
        return json.loads(entry["value"])
    except (json.JSONDecodeError, TypeError):
        return entry["value"]


def _set(key, value):
    """Set a key-value pair with metadata."""
    from nexus.mind.db import mem_set
    mem_set(key, json.dumps(value, ensure_ascii=False), datetime.now().isoformat())


def _delete(key):
    """Delete a key. Returns True if it existed."""
    from nexus.mind.db import mem_delete
    return mem_delete(key)
