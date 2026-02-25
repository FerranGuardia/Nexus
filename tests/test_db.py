"""Tests for nexus.mind.db — SQLite foundation."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers — each test class gets a fresh temp DB
# ---------------------------------------------------------------------------

def _reset_db():
    import nexus.mind.db as db
    tmpdir = tempfile.mkdtemp()
    db.close()
    db.DB_DIR = Path(tmpdir)
    db.DB_PATH = Path(tmpdir) / "nexus.db"
    db._conn = None
    return tmpdir


def _teardown_db(tmpdir):
    import nexus.mind.db as db
    db.close()
    db.DB_DIR = Path.home() / ".nexus"
    db.DB_PATH = db.DB_DIR / "nexus.db"
    db._conn = None
    shutil.rmtree(tmpdir, ignore_errors=True)


# ===========================================================================
# Schema
# ===========================================================================

class TestSchema:

    def setup_method(self):
        self._tmpdir = _reset_db()

    def teardown_method(self):
        _teardown_db(self._tmpdir)

    def test_tables_created(self):
        import nexus.mind.db as db
        conn = db._get_conn()
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [r["name"] for r in rows]
        for table in ["memory", "labels", "actions", "method_stats",
                       "workflows", "workflow_steps", "graph_nodes", "graph_edges"]:
            assert table in names, f"Missing table: {table}"

    def test_wal_mode(self):
        import nexus.mind.db as db
        conn = db._get_conn()
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"

    def test_foreign_keys_on(self):
        import nexus.mind.db as db
        conn = db._get_conn()
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1


# ===========================================================================
# Memory CRUD
# ===========================================================================

class TestMemoryCRUD:

    def setup_method(self):
        self._tmpdir = _reset_db()

    def teardown_method(self):
        _teardown_db(self._tmpdir)

    def test_set_and_get(self):
        from nexus.mind.db import mem_set, mem_get
        mem_set("color", '"blue"', "2026-01-01T00:00:00")
        entry = mem_get("color")
        assert entry is not None
        assert entry["value"] == '"blue"'

    def test_get_missing(self):
        from nexus.mind.db import mem_get
        assert mem_get("nope") is None

    def test_upsert(self):
        from nexus.mind.db import mem_set, mem_get
        mem_set("k", "v1", "2026-01-01")
        mem_set("k", "v2", "2026-01-02")
        assert mem_get("k")["value"] == "v2"
        assert mem_get("k")["updated"] == "2026-01-02"

    def test_delete(self):
        from nexus.mind.db import mem_set, mem_delete, mem_get
        mem_set("k", "v", "2026-01-01")
        assert mem_delete("k") is True
        assert mem_get("k") is None

    def test_delete_missing(self):
        from nexus.mind.db import mem_delete
        assert mem_delete("nope") is False

    def test_list(self):
        from nexus.mind.db import mem_set, mem_list
        mem_set("b", "1", "2026-01-01")
        mem_set("a", "2", "2026-01-01")
        keys = mem_list()
        assert keys == ["a", "b"]  # Sorted

    def test_list_empty(self):
        from nexus.mind.db import mem_list
        assert mem_list() == []

    def test_clear(self):
        from nexus.mind.db import mem_set, mem_clear, mem_list
        mem_set("a", "1", "2026-01-01")
        mem_set("b", "2", "2026-01-01")
        mem_clear()
        assert mem_list() == []


# ===========================================================================
# Label CRUD
# ===========================================================================

class TestLabelCRUD:

    def setup_method(self):
        self._tmpdir = _reset_db()

    def teardown_method(self):
        _teardown_db(self._tmpdir)

    def test_upsert_and_get(self):
        from nexus.mind.db import label_upsert, label_get
        label_upsert("textedit", "save", "guardar")
        entry = label_get("textedit", "save")
        assert entry["mapped"] == "guardar"
        assert entry["hits"] == 1

    def test_hit_increment(self):
        from nexus.mind.db import label_upsert, label_get
        label_upsert("textedit", "save", "guardar")
        label_upsert("textedit", "save", "guardar")
        label_upsert("textedit", "save", "guardar")
        assert label_get("textedit", "save")["hits"] == 3

    def test_get_missing(self):
        from nexus.mind.db import label_get
        assert label_get("textedit", "nope") is None

    def test_get_all_for_app(self):
        from nexus.mind.db import label_upsert, label_get_all_for_app
        label_upsert("mail", "send", "enviar")
        label_upsert("mail", "delete", "eliminar")
        labels = label_get_all_for_app("mail")
        assert len(labels) == 2
        targets = {l["target"] for l in labels}
        assert targets == {"send", "delete"}

    def test_get_all_empty(self):
        from nexus.mind.db import label_get_all_for_app
        assert label_get_all_for_app("nope") == []

    def test_count_exclude_global(self):
        from nexus.mind.db import label_upsert, label_count
        label_upsert("_global", "save", "guardar")
        label_upsert("textedit", "save", "guardar")
        assert label_count(exclude_global=True) == 1

    def test_count_global_only(self):
        from nexus.mind.db import label_upsert, label_count
        label_upsert("_global", "save", "guardar")
        label_upsert("textedit", "save", "guardar")
        assert label_count(global_only=True) == 1


# ===========================================================================
# Action CRUD
# ===========================================================================

class TestActionCRUD:

    def setup_method(self):
        self._tmpdir = _reset_db()

    def teardown_method(self):
        _teardown_db(self._tmpdir)

    def test_insert_and_count(self):
        from nexus.mind.db import action_insert, action_count
        action_insert("2026-01-01", "TextEdit", "click Save", True, "click", "Save", "AXPress")
        assert action_count() == 1

    def test_list(self):
        from nexus.mind.db import action_insert, action_list
        action_insert("2026-01-01", "TextEdit", "click Save", True)
        action_insert("2026-01-02", "Safari", "get url", True)
        all_actions = action_list()
        assert len(all_actions) == 2

    def test_list_by_app(self):
        from nexus.mind.db import action_insert, action_list
        action_insert("2026-01-01", "TextEdit", "click Save", True)
        action_insert("2026-01-02", "Safari", "get url", True)
        safari = action_list(app="Safari")
        assert len(safari) == 1
        assert safari[0]["app"] == "Safari"

    def test_trim(self):
        from nexus.mind.db import action_insert, action_count, action_trim
        for i in range(10):
            action_insert(f"2026-01-{i+1:02d}", "App", f"action {i}", True)
        assert action_count() == 10
        action_trim(5)
        assert action_count() == 5

    def test_trim_keeps_newest(self):
        from nexus.mind.db import action_insert, action_trim, action_list
        for i in range(10):
            action_insert(f"2026-01-{i+1:02d}", "App", f"action {i}", True)
        action_trim(3)
        actions = action_list()
        intents = [a["intent"] for a in actions]
        # Newest first (ORDER BY id DESC)
        assert "action 9" in intents
        assert "action 0" not in intents


# ===========================================================================
# Method Stats CRUD
# ===========================================================================

class TestMethodStatsCRUD:

    def setup_method(self):
        self._tmpdir = _reset_db()

    def teardown_method(self):
        _teardown_db(self._tmpdir)

    def test_upsert_ok(self):
        from nexus.mind.db import method_upsert, method_stats_for_app
        method_upsert("textedit", "AXPress", True)
        method_upsert("textedit", "AXPress", True)
        method_upsert("textedit", "AXPress", False)
        stats = method_stats_for_app("textedit")
        assert stats["AXPress"]["ok"] == 2
        assert stats["AXPress"]["fail"] == 1

    def test_empty_app(self):
        from nexus.mind.db import method_stats_for_app
        assert method_stats_for_app("nope") == {}

    def test_app_count(self):
        from nexus.mind.db import method_upsert, method_app_count
        method_upsert("textedit", "AXPress", True)
        method_upsert("safari", "click", True)
        assert method_app_count() == 2


# ===========================================================================
# Workflow CRUD
# ===========================================================================

class TestWorkflowCRUD:

    def setup_method(self):
        self._tmpdir = _reset_db()

    def teardown_method(self):
        _teardown_db(self._tmpdir)

    def test_create_and_get(self):
        from nexus.mind.db import workflow_create, workflow_get
        workflow_create("send-gmail", "Send Gmail", app="Safari")
        wf = workflow_get("send-gmail")
        assert wf is not None
        assert wf["name"] == "Send Gmail"
        assert wf["app"] == "Safari"

    def test_get_missing(self):
        from nexus.mind.db import workflow_get
        assert workflow_get("nope") is None

    def test_list(self):
        from nexus.mind.db import workflow_create, workflow_list
        workflow_create("wf1", "Workflow 1")
        workflow_create("wf2", "Workflow 2")
        wfs = workflow_list()
        assert len(wfs) == 2

    def test_list_includes_step_count(self):
        from nexus.mind.db import workflow_create, step_insert, workflow_list
        workflow_create("wf1", "Workflow 1")
        step_insert("wf1", 1, "click Save")
        step_insert("wf1", 2, "press enter")
        wfs = workflow_list()
        assert wfs[0]["step_count"] == 2

    def test_delete(self):
        from nexus.mind.db import workflow_create, workflow_delete, workflow_get
        workflow_create("wf1", "Workflow 1")
        assert workflow_delete("wf1") is True
        assert workflow_get("wf1") is None

    def test_delete_missing(self):
        from nexus.mind.db import workflow_delete
        assert workflow_delete("nope") is False

    def test_delete_cascades_steps(self):
        from nexus.mind.db import workflow_create, step_insert, workflow_delete, steps_for_workflow
        workflow_create("wf1", "WF")
        step_insert("wf1", 1, "click Save")
        workflow_delete("wf1")
        assert steps_for_workflow("wf1") == []

    def test_update_stats(self):
        from nexus.mind.db import workflow_create, workflow_update_stats, workflow_get
        workflow_create("wf1", "WF")
        workflow_update_stats("wf1", ok=True)
        workflow_update_stats("wf1", ok=True)
        workflow_update_stats("wf1", ok=False)
        wf = workflow_get("wf1")
        assert wf["success_count"] == 2
        assert wf["fail_count"] == 1


# ===========================================================================
# Workflow Steps CRUD
# ===========================================================================

class TestStepCRUD:

    def setup_method(self):
        self._tmpdir = _reset_db()

    def teardown_method(self):
        _teardown_db(self._tmpdir)

    def test_insert_and_list(self):
        from nexus.mind.db import workflow_create, step_insert, steps_for_workflow
        workflow_create("wf1", "WF")
        step_insert("wf1", 1, "click Compose")
        step_insert("wf1", 2, "type hello")
        step_insert("wf1", 3, "press enter")
        steps = steps_for_workflow("wf1")
        assert len(steps) == 3
        assert steps[0]["step_num"] == 1
        assert steps[2]["action"] == "press enter"

    def test_ordering(self):
        from nexus.mind.db import workflow_create, step_insert, steps_for_workflow
        workflow_create("wf1", "WF")
        step_insert("wf1", 3, "third")
        step_insert("wf1", 1, "first")
        step_insert("wf1", 2, "second")
        steps = steps_for_workflow("wf1")
        assert [s["action"] for s in steps] == ["first", "second", "third"]

    def test_expected_hash(self):
        from nexus.mind.db import workflow_create, step_insert, steps_for_workflow
        workflow_create("wf1", "WF")
        step_insert("wf1", 1, "click Save", expected_hash="abc123")
        steps = steps_for_workflow("wf1")
        assert steps[0]["expected_hash"] == "abc123"


# ===========================================================================
# Graph CRUD
# ===========================================================================

class TestGraphCRUD:

    def setup_method(self):
        self._tmpdir = _reset_db()

    def teardown_method(self):
        _teardown_db(self._tmpdir)

    def test_node_upsert(self):
        from nexus.mind.db import node_upsert, node_get
        node_upsert("abc123", "Safari")
        node = node_get("abc123")
        assert node is not None
        assert node["app"] == "Safari"
        assert node["visit_count"] == 1

    def test_node_visit_count_increments(self):
        from nexus.mind.db import node_upsert, node_get
        node_upsert("abc123", "Safari")
        node_upsert("abc123", "Safari")
        node_upsert("abc123", "Safari")
        assert node_get("abc123")["visit_count"] == 3

    def test_node_label_preserved(self):
        from nexus.mind.db import node_upsert, node_get
        node_upsert("abc123", "Safari", label="Inbox")
        node_upsert("abc123", "Safari")  # No label
        assert node_get("abc123")["label"] == "Inbox"

    def test_edge_upsert(self):
        from nexus.mind.db import node_upsert, edge_upsert, edges_from
        node_upsert("a", "Safari")
        node_upsert("b", "Safari")
        edge_upsert("a", "b", "click Compose", True, 0.5)
        edges = edges_from("a")
        assert len(edges) == 1
        assert edges[0]["action"] == "click Compose"
        assert edges[0]["success_count"] == 1

    def test_edge_counters_increment(self):
        from nexus.mind.db import node_upsert, edge_upsert, edges_from
        node_upsert("a", "Safari")
        node_upsert("b", "Safari")
        edge_upsert("a", "b", "click Compose", True, 0.5)
        edge_upsert("a", "b", "click Compose", True, 0.3)
        edge_upsert("a", "b", "click Compose", False, 1.0)
        edges = edges_from("a")
        assert edges[0]["success_count"] == 2
        assert edges[0]["fail_count"] == 1

    def test_all_edges(self):
        from nexus.mind.db import node_upsert, edge_upsert, all_edges
        node_upsert("a", "App")
        node_upsert("b", "App")
        node_upsert("c", "App")
        edge_upsert("a", "b", "act1", True, 0.1)
        edge_upsert("b", "c", "act2", True, 0.2)
        edges = all_edges()
        assert len(edges) == 2


# ===========================================================================
# Migration
# ===========================================================================

class TestMigration:

    def setup_method(self):
        self._tmpdir = _reset_db()

    def teardown_method(self):
        _teardown_db(self._tmpdir)

    def test_migrate_memory_json(self):
        import nexus.mind.db as db
        # Write a memory.json in the temp dir
        mem_file = db.DB_DIR / "memory.json"
        mem_file.write_text(json.dumps({
            "editor": {"value": "vim", "updated": "2026-01-01T00:00:00"},
            "lang": {"value": "python", "updated": "2026-01-02T00:00:00"},
        }))
        # Force reconnect to trigger migration
        db.close()
        db._conn = None
        db._get_conn()
        # Verify data migrated
        entry = db.mem_get("editor")
        assert entry is not None
        assert json.loads(entry["value"]) == "vim"
        # Verify .bak created
        assert not mem_file.exists()
        assert mem_file.with_suffix(".json.bak").exists()

    def test_migrate_learned_json(self):
        import nexus.mind.db as db
        learn_file = db.DB_DIR / "learned.json"
        learn_file.write_text(json.dumps({
            "version": 1,
            "labels": {
                "textedit": {"save": {"mapped": "guardar", "hits": 3, "updated": "2026-01-01"}},
                "_global": {"save": {"mapped": "guardar", "hits": 5, "updated": "2026-01-01"}},
            },
            "actions": [
                {"ts": "2026-01-01", "app": "TextEdit", "intent": "click Save", "ok": True,
                 "verb": "click", "target": "Save", "method": "AXPress"},
            ],
            "methods": {
                "textedit": {"AXPress": {"ok": 10, "fail": 1}},
            },
        }))
        db.close()
        db._conn = None
        db._get_conn()
        # Labels
        entry = db.label_get("textedit", "save")
        assert entry is not None
        assert entry["mapped"] == "guardar"
        assert entry["hits"] == 3
        # Actions
        assert db.action_count() == 1
        # Method stats
        stats = db.method_stats_for_app("textedit")
        assert stats["AXPress"]["ok"] == 10
        # Backup
        assert not learn_file.exists()
        assert learn_file.with_suffix(".json.bak").exists()

    def test_migration_idempotent(self):
        import nexus.mind.db as db
        # Pre-populate DB with data
        db.mem_set("x", "1", "2026-01-01")
        # Create a memory.json (should be skipped since table is non-empty)
        mem_file = db.DB_DIR / "memory.json"
        mem_file.write_text(json.dumps({"y": {"value": "2", "updated": "2026-01-01"}}))
        db.close()
        db._conn = None
        db._get_conn()
        # y should NOT have been migrated (table wasn't empty)
        assert db.mem_get("y") is None
        assert db.mem_get("x") is not None

    def test_corrupt_json_skipped(self):
        import nexus.mind.db as db
        mem_file = db.DB_DIR / "memory.json"
        mem_file.write_text("{corrupt json!!!")
        db.close()
        db._conn = None
        # Should not crash
        db._get_conn()
        assert db.mem_list() == []

    def test_no_json_files_no_error(self):
        import nexus.mind.db as db
        # No JSON files exist — should just init cleanly
        db.close()
        db._conn = None
        db._get_conn()
        assert db.mem_list() == []


# ===========================================================================
# Connection management
# ===========================================================================

class TestConnection:

    def setup_method(self):
        self._tmpdir = _reset_db()

    def teardown_method(self):
        _teardown_db(self._tmpdir)

    def test_close_and_reopen(self):
        from nexus.mind.db import mem_set, mem_get, close, _get_conn
        mem_set("k", "v", "2026-01-01")
        close()
        # Re-open should work
        _get_conn()
        assert mem_get("k")["value"] == "v"

    def test_db_file_created(self):
        import nexus.mind.db as db
        db._get_conn()
        assert db.DB_PATH.exists()
