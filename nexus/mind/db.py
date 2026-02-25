"""SQLite storage backend — persistent foundation for all Nexus data.

Replaces the previous JSON file stores (memory.json, learned.json).
Also provides tables for Phase 8 features: workflows, navigation graph.

Storage: ~/.nexus/nexus.db (WAL mode, zero new deps — stdlib sqlite3).
"""

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths — module-level for test patching (same pattern as old store.py)
# ---------------------------------------------------------------------------

DB_DIR = Path.home() / ".nexus"
DB_PATH = DB_DIR / "nexus.db"

# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

_conn = None
_lock = threading.Lock()

_SCHEMA_SQL = """
-- User memory (migrated from memory.json)
CREATE TABLE IF NOT EXISTS memory (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated TEXT NOT NULL
);

-- Label translations (migrated from learned.json)
CREATE TABLE IF NOT EXISTS labels (
    app TEXT NOT NULL,
    target TEXT NOT NULL,
    mapped TEXT NOT NULL,
    hits INTEGER DEFAULT 1,
    updated TEXT NOT NULL,
    PRIMARY KEY (app, target)
);

-- Action history (migrated from learned.json)
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    app TEXT NOT NULL,
    intent TEXT NOT NULL,
    ok INTEGER NOT NULL,
    verb TEXT,
    target TEXT,
    method TEXT,
    via_label TEXT
);

-- Method success rates (migrated from learned.json)
CREATE TABLE IF NOT EXISTS method_stats (
    app TEXT NOT NULL,
    method TEXT NOT NULL,
    ok_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    PRIMARY KEY (app, method)
);

-- Workflow recording (Phase 8)
CREATE TABLE IF NOT EXISTS workflows (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    app TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS workflow_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    step_num INTEGER NOT NULL,
    action TEXT NOT NULL,
    expected_hash TEXT,
    timeout_ms INTEGER DEFAULT 5000,
    UNIQUE(workflow_id, step_num)
);

-- Navigation graph (Phase 8)
CREATE TABLE IF NOT EXISTS graph_nodes (
    hash TEXT PRIMARY KEY,
    app TEXT NOT NULL,
    label TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    visit_count INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS graph_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_hash TEXT NOT NULL,
    to_hash TEXT NOT NULL,
    action TEXT NOT NULL,
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    avg_elapsed REAL DEFAULT 0,
    last_used TEXT NOT NULL
);
"""


def _get_conn():
    """Get or create the SQLite connection (lazy init, thread-safe)."""
    global _conn
    if _conn is not None:
        return _conn
    with _lock:
        if _conn is not None:
            return _conn
        DB_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(_SCHEMA_SQL)
        _conn = conn
        migrate_json_files()
        return _conn


def close():
    """Close the connection (for clean shutdown and test teardown)."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None


# ---------------------------------------------------------------------------
# Migration — one-time import from legacy JSON files
# ---------------------------------------------------------------------------

def migrate_json_files():
    """Migrate memory.json and learned.json into SQLite.

    Idempotent: only migrates if the corresponding table is empty.
    Renames processed files to .json.bak (safety net).
    """
    conn = _conn
    if conn is None:
        return

    # --- memory.json ---
    mem_file = DB_DIR / "memory.json"
    if mem_file.exists():
        row = conn.execute("SELECT COUNT(*) FROM memory").fetchone()
        if row[0] == 0:
            try:
                data = json.loads(mem_file.read_text())
                if isinstance(data, dict):
                    with conn:
                        for key, entry in data.items():
                            if isinstance(entry, dict):
                                value = json.dumps(entry.get("value", ""))
                                updated = entry.get("updated", datetime.now().isoformat())
                            else:
                                value = json.dumps(entry)
                                updated = datetime.now().isoformat()
                            conn.execute(
                                "INSERT OR IGNORE INTO memory (key, value, updated) VALUES (?, ?, ?)",
                                (key, value, updated),
                            )
                mem_file.rename(mem_file.with_suffix(".json.bak"))
            except (json.JSONDecodeError, IOError, OSError):
                pass  # Corrupt file — skip, don't crash

    # --- learned.json ---
    learn_file = DB_DIR / "learned.json"
    if learn_file.exists():
        row = conn.execute("SELECT COUNT(*) FROM labels").fetchone()
        actions_row = conn.execute("SELECT COUNT(*) FROM actions").fetchone()
        if row[0] == 0 and actions_row[0] == 0:
            try:
                data = json.loads(learn_file.read_text())
                if isinstance(data, dict):
                    with conn:
                        # Labels
                        for app, mappings in data.get("labels", {}).items():
                            if isinstance(mappings, dict):
                                for target, entry in mappings.items():
                                    if isinstance(entry, dict):
                                        conn.execute(
                                            "INSERT OR IGNORE INTO labels (app, target, mapped, hits, updated) "
                                            "VALUES (?, ?, ?, ?, ?)",
                                            (app, target, entry.get("mapped", ""),
                                             entry.get("hits", 1),
                                             entry.get("updated", datetime.now().isoformat())),
                                        )
                        # Actions
                        for act in data.get("actions", []):
                            if isinstance(act, dict):
                                conn.execute(
                                    "INSERT INTO actions (ts, app, intent, ok, verb, target, method, via_label) "
                                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                    (act.get("ts", ""), act.get("app", ""),
                                     act.get("intent", ""), 1 if act.get("ok") else 0,
                                     act.get("verb"), act.get("target"),
                                     act.get("method"), act.get("via_label")),
                                )
                        # Method stats
                        for app, methods in data.get("methods", {}).items():
                            if isinstance(methods, dict):
                                for method, counts in methods.items():
                                    if isinstance(counts, dict):
                                        conn.execute(
                                            "INSERT OR IGNORE INTO method_stats (app, method, ok_count, fail_count) "
                                            "VALUES (?, ?, ?, ?)",
                                            (app, method,
                                             counts.get("ok", 0), counts.get("fail", 0)),
                                        )
                learn_file.rename(learn_file.with_suffix(".json.bak"))
            except (json.JSONDecodeError, IOError, OSError):
                pass


# ---------------------------------------------------------------------------
# Memory CRUD
# ---------------------------------------------------------------------------

def mem_get(key):
    """Get a memory entry. Returns {"value": str, "updated": str} or None."""
    conn = _get_conn()
    row = conn.execute("SELECT value, updated FROM memory WHERE key = ?", (key,)).fetchone()
    if row is None:
        return None
    return {"value": row["value"], "updated": row["updated"]}


def mem_set(key, value, updated):
    """Upsert a memory entry."""
    conn = _get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO memory (key, value, updated) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated=excluded.updated",
            (key, value, updated),
        )
        conn.commit()


def mem_delete(key):
    """Delete a memory entry. Returns True if it existed."""
    conn = _get_conn()
    with _lock:
        cursor = conn.execute("DELETE FROM memory WHERE key = ?", (key,))
        conn.commit()
        return cursor.rowcount > 0


def mem_list():
    """List all memory keys."""
    conn = _get_conn()
    rows = conn.execute("SELECT key FROM memory ORDER BY key").fetchall()
    return [r["key"] for r in rows]


def mem_clear():
    """Delete all memory entries."""
    conn = _get_conn()
    with _lock:
        conn.execute("DELETE FROM memory")
        conn.commit()


# ---------------------------------------------------------------------------
# Label CRUD
# ---------------------------------------------------------------------------

def label_get(app, target):
    """Get a label mapping. Returns {"mapped": str, "hits": int} or None."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT mapped, hits FROM labels WHERE app = ? AND target = ?",
        (app, target),
    ).fetchone()
    if row is None:
        return None
    return {"mapped": row["mapped"], "hits": row["hits"]}


def label_upsert(app, target, mapped):
    """Insert or increment hits on a label mapping."""
    conn = _get_conn()
    now = datetime.now().isoformat()
    with _lock:
        conn.execute(
            "INSERT INTO labels (app, target, mapped, hits, updated) VALUES (?, ?, ?, 1, ?) "
            "ON CONFLICT(app, target) DO UPDATE SET "
            "mapped=excluded.mapped, hits=hits+1, updated=excluded.updated",
            (app, target, mapped, now),
        )
        conn.commit()


def label_get_all_for_app(app):
    """Return all label mappings for an app."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT target, mapped, hits FROM labels WHERE app = ? ORDER BY hits DESC",
        (app,),
    ).fetchall()
    return [{"target": r["target"], "mapped": r["mapped"], "hits": r["hits"]} for r in rows]


def label_count(exclude_global=False, global_only=False):
    """Count label mappings."""
    conn = _get_conn()
    if global_only:
        row = conn.execute("SELECT COUNT(*) FROM labels WHERE app = '_global'").fetchone()
    elif exclude_global:
        row = conn.execute("SELECT COUNT(*) FROM labels WHERE app != '_global'").fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) FROM labels").fetchone()
    return row[0]


# ---------------------------------------------------------------------------
# Action CRUD
# ---------------------------------------------------------------------------

def action_insert(ts, app, intent, ok, verb=None, target=None, method=None, via_label=None):
    """Insert an action record."""
    conn = _get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO actions (ts, app, intent, ok, verb, target, method, via_label) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (ts, app, intent, 1 if ok else 0, verb, target, method, via_label),
        )
        conn.commit()


def action_count():
    """Count total action records."""
    conn = _get_conn()
    row = conn.execute("SELECT COUNT(*) FROM actions").fetchone()
    return row[0]


def action_trim(max_rows):
    """Delete oldest rows beyond max_rows (FIFO enforcement)."""
    conn = _get_conn()
    with _lock:
        conn.execute(
            "DELETE FROM actions WHERE id NOT IN "
            "(SELECT id FROM actions ORDER BY id DESC LIMIT ?)",
            (max_rows,),
        )
        conn.commit()


def action_list(app=None, limit=500):
    """List recent actions, optionally filtered by app."""
    conn = _get_conn()
    if app:
        rows = conn.execute(
            "SELECT * FROM actions WHERE app = ? ORDER BY id DESC LIMIT ?",
            (app, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM actions ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Method stats CRUD
# ---------------------------------------------------------------------------

def method_upsert(app, method, ok):
    """Increment ok_count or fail_count for an app+method pair."""
    conn = _get_conn()
    col = "ok_count" if ok else "fail_count"
    with _lock:
        conn.execute(
            f"INSERT INTO method_stats (app, method, ok_count, fail_count) VALUES (?, ?, ?, ?) "
            f"ON CONFLICT(app, method) DO UPDATE SET {col}={col}+1",
            (app, method, 1 if ok else 0, 0 if ok else 1),
        )
        conn.commit()


def method_stats_for_app(app):
    """Return {method: {"ok": int, "fail": int}} for an app."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT method, ok_count, fail_count FROM method_stats WHERE app = ?",
        (app,),
    ).fetchall()
    return {r["method"]: {"ok": r["ok_count"], "fail": r["fail_count"]} for r in rows}


def method_app_count():
    """Count distinct apps in method_stats."""
    conn = _get_conn()
    row = conn.execute("SELECT COUNT(DISTINCT app) FROM method_stats").fetchone()
    return row[0]


# ---------------------------------------------------------------------------
# Workflow CRUD
# ---------------------------------------------------------------------------

def workflow_create(id, name, app=None):
    """Create a new workflow."""
    conn = _get_conn()
    now = datetime.now().isoformat()
    with _lock:
        conn.execute(
            "INSERT INTO workflows (id, name, app, created, updated) VALUES (?, ?, ?, ?, ?)",
            (id, name, app, now, now),
        )
        conn.commit()


def workflow_get(id):
    """Get a workflow by ID. Returns dict or None."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM workflows WHERE id = ?", (id,)).fetchone()
    if row is None:
        return None
    return dict(row)


def workflow_list():
    """List all workflows with step counts."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT w.*, COUNT(s.id) AS step_count "
        "FROM workflows w LEFT JOIN workflow_steps s ON w.id = s.workflow_id "
        "GROUP BY w.id ORDER BY w.updated DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def workflow_delete(id):
    """Delete a workflow and its steps (cascade). Returns True if existed."""
    conn = _get_conn()
    with _lock:
        cursor = conn.execute("DELETE FROM workflows WHERE id = ?", (id,))
        conn.commit()
        return cursor.rowcount > 0


def workflow_update_stats(id, ok):
    """Increment success_count or fail_count."""
    conn = _get_conn()
    col = "success_count" if ok else "fail_count"
    now = datetime.now().isoformat()
    with _lock:
        conn.execute(
            f"UPDATE workflows SET {col}={col}+1, updated=? WHERE id=?",
            (now, id),
        )
        conn.commit()


def step_insert(workflow_id, step_num, action, expected_hash=None, timeout_ms=5000):
    """Insert a workflow step."""
    conn = _get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO workflow_steps (workflow_id, step_num, action, expected_hash, timeout_ms) "
            "VALUES (?, ?, ?, ?, ?)",
            (workflow_id, step_num, action, expected_hash, timeout_ms),
        )
        conn.commit()


def steps_for_workflow(workflow_id):
    """Get all steps for a workflow, ordered by step_num."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM workflow_steps WHERE workflow_id = ? ORDER BY step_num",
        (workflow_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Graph CRUD
# ---------------------------------------------------------------------------

def node_upsert(hash, app, label=None):
    """Insert or update a graph node (increments visit_count)."""
    conn = _get_conn()
    now = datetime.now().isoformat()
    with _lock:
        conn.execute(
            "INSERT INTO graph_nodes (hash, app, label, first_seen, last_seen, visit_count) "
            "VALUES (?, ?, ?, ?, ?, 1) "
            "ON CONFLICT(hash) DO UPDATE SET "
            "last_seen=excluded.last_seen, visit_count=visit_count+1, "
            "label=COALESCE(excluded.label, label)",
            (hash, app, label, now, now),
        )
        conn.commit()


def node_get(hash):
    """Get a graph node. Returns dict or None."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM graph_nodes WHERE hash = ?", (hash,)).fetchone()
    if row is None:
        return None
    return dict(row)


def edge_upsert(from_hash, to_hash, action, ok, elapsed):
    """Insert or update a graph edge."""
    conn = _get_conn()
    now = datetime.now().isoformat()
    with _lock:
        # Check for existing edge
        row = conn.execute(
            "SELECT id, success_count, fail_count, avg_elapsed FROM graph_edges "
            "WHERE from_hash=? AND to_hash=? AND action=?",
            (from_hash, to_hash, action),
        ).fetchone()
        if row:
            col = "success_count" if ok else "fail_count"
            total = row["success_count"] + row["fail_count"] + 1
            new_avg = (row["avg_elapsed"] * (total - 1) + elapsed) / total
            conn.execute(
                f"UPDATE graph_edges SET {col}={col}+1, avg_elapsed=?, last_used=? WHERE id=?",
                (new_avg, now, row["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO graph_edges (from_hash, to_hash, action, success_count, fail_count, avg_elapsed, last_used) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (from_hash, to_hash, action, 1 if ok else 0, 0 if ok else 1, elapsed, now),
            )
        conn.commit()


def edges_from(hash):
    """Get all edges originating from a node."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM graph_edges WHERE from_hash = ? ORDER BY success_count DESC",
        (hash,),
    ).fetchall()
    return [dict(r) for r in rows]


def all_edges():
    """Get all edges (for pathfinding)."""
    conn = _get_conn()
    rows = conn.execute("SELECT from_hash, to_hash, action, success_count FROM graph_edges").fetchall()
    return [dict(r) for r in rows]
