"""Persistent key-value memory — the `memory` tool.

Simple JSON file store that persists across sessions.
The AI remembers what it learns about the user, the machine,
and patterns it discovers.
"""

import json
import os
from pathlib import Path
from datetime import datetime

# Store in user's home dir so it survives repo changes
STORE_DIR = Path.home() / ".nexus"
STORE_FILE = STORE_DIR / "memory.json"


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
        data = _load()
        if not data:
            return {"ok": True, "keys": [], "count": 0}
        keys = list(data.keys())
        return {"ok": True, "keys": keys, "count": len(keys)}

    if op == "clear":
        _save({})
        return {"ok": True, "action": "clear"}

    return {"ok": False, "error": f'Unknown op: "{op}". Use: get, set, delete, list, clear'}


def _load():
    """Load the memory store from disk."""
    if not STORE_FILE.exists():
        return {}
    try:
        return json.loads(STORE_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        return {}


def _save(data):
    """Save the memory store to disk."""
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    STORE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def _get(key):
    """Get a value by key."""
    data = _load()
    entry = data.get(key)
    if entry is None:
        return None
    return entry.get("value") if isinstance(entry, dict) else entry


def _set(key, value):
    """Set a key-value pair with metadata."""
    data = _load()
    data[key] = {
        "value": value,
        "updated": datetime.now().isoformat(),
    }
    _save(data)


def _delete(key):
    """Delete a key. Returns True if it existed."""
    data = _load()
    if key in data:
        del data[key]
        _save(data)
        return True
    return False
