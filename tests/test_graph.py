"""Tests for nexus.mind.graph — passive navigation graph."""

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
# Record transitions
# ===========================================================================

class TestRecordTransition:

    def setup_method(self):
        self._tmpdir = _reset_db()

    def teardown_method(self):
        _teardown_db(self._tmpdir)

    def test_basic_transition(self):
        import nexus.mind.db as db
        from nexus.mind.graph import record_transition
        record_transition("aaa", "bbb", "click About", "Settings", True, 0.5)
        # Both nodes should exist
        assert db.node_get("aaa") is not None
        assert db.node_get("bbb") is not None
        # Edge should exist
        edges = db.edges_from("aaa")
        assert len(edges) == 1
        assert edges[0]["action"] == "click About"

    def test_skip_same_hash(self):
        import nexus.mind.db as db
        from nexus.mind.graph import record_transition
        record_transition("aaa", "aaa", "click X", "App", True, 0.5)
        assert db.node_get("aaa") is None

    def test_skip_empty_hash(self):
        import nexus.mind.db as db
        from nexus.mind.graph import record_transition
        record_transition(None, "bbb", "click X", "App", True, 0.5)
        record_transition("aaa", None, "click X", "App", True, 0.5)
        record_transition(None, None, "click X", "App", True, 0.5)
        assert db.node_get("aaa") is None
        assert db.node_get("bbb") is None

    def test_visit_count_increments(self):
        import nexus.mind.db as db
        from nexus.mind.graph import record_transition
        record_transition("aaa", "bbb", "click A", "App", True, 0.5)
        record_transition("bbb", "ccc", "click B", "App", True, 0.3)
        # bbb was seen in both transitions
        assert db.node_get("bbb")["visit_count"] == 2

    def test_edge_success_count(self):
        import nexus.mind.db as db
        from nexus.mind.graph import record_transition
        record_transition("aaa", "bbb", "click Save", "App", True, 0.5)
        record_transition("aaa", "bbb", "click Save", "App", True, 0.3)
        record_transition("aaa", "bbb", "click Save", "App", False, 1.0)
        edges = db.edges_from("aaa")
        assert edges[0]["success_count"] == 2
        assert edges[0]["fail_count"] == 1


# ===========================================================================
# Pathfinding
# ===========================================================================

class TestFindPath:

    def setup_method(self):
        self._tmpdir = _reset_db()

    def teardown_method(self):
        _teardown_db(self._tmpdir)

    def test_same_node(self):
        from nexus.mind.graph import find_path
        assert find_path("aaa", "aaa") == []

    def test_direct_path(self):
        from nexus.mind.graph import record_transition, find_path
        record_transition("aaa", "bbb", "click About", "Settings", True, 0.5)
        path = find_path("aaa", "bbb")
        assert path is not None
        assert len(path) == 1
        assert path[0]["action"] == "click About"
        assert path[0]["from"] == "aaa"
        assert path[0]["to"] == "bbb"

    def test_multi_hop_path(self):
        from nexus.mind.graph import record_transition, find_path
        record_transition("aaa", "bbb", "click General", "Settings", True, 0.3)
        record_transition("bbb", "ccc", "click About", "Settings", True, 0.2)
        record_transition("ccc", "ddd", "click Details", "Settings", True, 0.1)
        path = find_path("aaa", "ddd")
        assert path is not None
        assert len(path) == 3
        actions = [s["action"] for s in path]
        assert actions == ["click General", "click About", "click Details"]

    def test_no_path(self):
        from nexus.mind.graph import record_transition, find_path
        record_transition("aaa", "bbb", "click A", "App", True, 0.5)
        # ccc is disconnected
        assert find_path("aaa", "ccc") is None

    def test_empty_graph(self):
        from nexus.mind.graph import find_path
        assert find_path("aaa", "bbb") is None

    def test_shortest_path_preferred(self):
        from nexus.mind.graph import record_transition, find_path
        # Direct path: aaa → ddd
        record_transition("aaa", "ddd", "direct shortcut", "App", True, 0.1)
        # Longer path: aaa → bbb → ccc → ddd
        record_transition("aaa", "bbb", "click B", "App", True, 0.1)
        record_transition("bbb", "ccc", "click C", "App", True, 0.1)
        record_transition("ccc", "ddd", "click D", "App", True, 0.1)
        path = find_path("aaa", "ddd")
        assert len(path) == 1  # BFS prefers shorter
        assert path[0]["action"] == "direct shortcut"

    def test_cycle_handling(self):
        from nexus.mind.graph import record_transition, find_path
        # Create a cycle: aaa → bbb → aaa
        record_transition("aaa", "bbb", "go forward", "App", True, 0.1)
        record_transition("bbb", "aaa", "go back", "App", True, 0.1)
        # Add a path out: bbb → ccc
        record_transition("bbb", "ccc", "click exit", "App", True, 0.1)
        path = find_path("aaa", "ccc")
        assert path is not None
        assert len(path) == 2  # aaa→bbb→ccc


# ===========================================================================
# Suggest action
# ===========================================================================

class TestSuggestAction:

    def setup_method(self):
        self._tmpdir = _reset_db()

    def teardown_method(self):
        _teardown_db(self._tmpdir)

    def test_suggest_first_step(self):
        from nexus.mind.graph import record_transition, suggest_action
        record_transition("aaa", "bbb", "click General", "Settings", True, 0.3)
        record_transition("bbb", "ccc", "click About", "Settings", True, 0.2)
        action = suggest_action("aaa", "ccc")
        assert action == "click General"

    def test_suggest_no_path(self):
        from nexus.mind.graph import suggest_action
        assert suggest_action("aaa", "bbb") is None

    def test_suggest_same_node(self):
        from nexus.mind.graph import suggest_action
        # Same node — empty path, no first step
        assert suggest_action("aaa", "aaa") is None


# ===========================================================================
# Graph stats
# ===========================================================================

class TestGraphStats:

    def setup_method(self):
        self._tmpdir = _reset_db()

    def teardown_method(self):
        _teardown_db(self._tmpdir)

    def test_empty_stats(self):
        from nexus.mind.graph import graph_stats
        stats = graph_stats()
        assert stats["nodes"] == 0
        assert stats["edges"] == 0
        assert stats["apps"] == []

    def test_stats_after_transitions(self):
        from nexus.mind.graph import record_transition, graph_stats
        record_transition("aaa", "bbb", "click A", "Safari", True, 0.5)
        record_transition("bbb", "ccc", "click B", "Settings", True, 0.3)
        stats = graph_stats()
        assert stats["nodes"] == 3
        assert stats["edges"] == 2
        assert set(stats["apps"]) == {"Safari", "Settings"}


# ===========================================================================
# Hook integration
# ===========================================================================

class TestGraphHook:

    def setup_method(self):
        self._tmpdir = _reset_db()

    def teardown_method(self):
        _teardown_db(self._tmpdir)

    def test_hook_records_transition(self):
        import nexus.mind.db as db
        from nexus.hooks import _graph_record_hook
        ctx = {
            "before_hash": "aaa",
            "after_hash": "bbb",
            "action": "click Save",
            "app_name": "TextEdit",
            "result": {"ok": True},
            "elapsed": 0.5,
        }
        _graph_record_hook(ctx)
        assert db.node_get("aaa") is not None
        assert db.node_get("bbb") is not None
        edges = db.edges_from("aaa")
        assert len(edges) == 1

    def test_hook_skips_same_hash(self):
        import nexus.mind.db as db
        from nexus.hooks import _graph_record_hook
        ctx = {
            "before_hash": "aaa",
            "after_hash": "aaa",
            "action": "click X",
            "app_name": "App",
            "result": {"ok": True},
            "elapsed": 0.1,
        }
        _graph_record_hook(ctx)
        assert db.node_get("aaa") is None

    def test_hook_skips_failed_action(self):
        import nexus.mind.db as db
        from nexus.hooks import _graph_record_hook
        ctx = {
            "before_hash": "aaa",
            "after_hash": "bbb",
            "action": "click X",
            "app_name": "App",
            "result": {"ok": False},
            "elapsed": 0.1,
        }
        _graph_record_hook(ctx)
        assert db.node_get("aaa") is None

    def test_hook_skips_missing_hashes(self):
        import nexus.mind.db as db
        from nexus.hooks import _graph_record_hook
        ctx = {
            "action": "click X",
            "app_name": "App",
            "result": {"ok": True},
            "elapsed": 0.1,
        }
        _graph_record_hook(ctx)
        # No nodes created
        stats = db._get_conn().execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0]
        assert stats == 0
