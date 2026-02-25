"""Tests for nexus.mind.workflows — workflow recording and replay."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

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


def _reset_recording():
    """Clear module-level recording state."""
    import nexus.mind.workflows as wf
    wf._recording = None


# ===========================================================================
# Slugify
# ===========================================================================

class TestSlugify:

    def test_basic_slug(self):
        from nexus.mind.workflows import _slugify
        assert _slugify("Send Gmail Email") == "send-gmail-email"

    def test_special_chars(self):
        from nexus.mind.workflows import _slugify
        assert _slugify("File: Save As!") == "file-save-as"

    def test_whitespace(self):
        from nexus.mind.workflows import _slugify
        assert _slugify("  hello  world  ") == "hello-world"

    def test_empty(self):
        from nexus.mind.workflows import _slugify
        assert _slugify("") == "unnamed"

    def test_only_special_chars(self):
        from nexus.mind.workflows import _slugify
        assert _slugify("!!!") == "unnamed"


# ===========================================================================
# Unique slug
# ===========================================================================

class TestUniqueSlug:

    def setup_method(self):
        self._tmpdir = _reset_db()

    def teardown_method(self):
        _teardown_db(self._tmpdir)
        _reset_recording()

    def test_no_collision(self):
        from nexus.mind.workflows import _unique_slug
        assert _unique_slug("send-gmail") == "send-gmail"

    def test_collision_appends_number(self):
        import nexus.mind.db as db
        from nexus.mind.workflows import _unique_slug
        db.workflow_create("send-gmail", "Send Gmail")
        assert _unique_slug("send-gmail") == "send-gmail-2"

    def test_multiple_collisions(self):
        import nexus.mind.db as db
        from nexus.mind.workflows import _unique_slug
        db.workflow_create("test", "Test")
        db.workflow_create("test-2", "Test 2")
        assert _unique_slug("test") == "test-3"


# ===========================================================================
# Recording lifecycle
# ===========================================================================

class TestRecording:

    def setup_method(self):
        self._tmpdir = _reset_db()
        _reset_recording()

    def teardown_method(self):
        _teardown_db(self._tmpdir)
        _reset_recording()

    def test_start_recording(self):
        from nexus.mind.workflows import start_recording, is_recording
        result = start_recording("Send Gmail")
        assert result["ok"] is True
        assert result["id"] == "send-gmail"
        assert is_recording() is True

    def test_start_recording_creates_db_row(self):
        import nexus.mind.db as db
        from nexus.mind.workflows import start_recording
        start_recording("Send Gmail", app="Safari")
        wf = db.workflow_get("send-gmail")
        assert wf is not None
        assert wf["name"] == "Send Gmail"
        assert wf["app"] == "Safari"

    def test_double_start_fails(self):
        from nexus.mind.workflows import start_recording
        start_recording("First")
        result = start_recording("Second")
        assert result["ok"] is False
        assert "Already recording" in result["error"]

    def test_stop_recording(self):
        from nexus.mind.workflows import start_recording, stop_recording, is_recording
        start_recording("Test")
        result = stop_recording()
        assert result["ok"] is True
        assert result["steps"] == 0
        assert is_recording() is False

    def test_stop_without_start_fails(self):
        from nexus.mind.workflows import stop_recording
        result = stop_recording()
        assert result["ok"] is False
        assert "Not currently recording" in result["error"]

    def test_record_steps(self):
        from nexus.mind.workflows import start_recording, record_step, stop_recording
        start_recording("Test")
        record_step("click Compose")
        record_step("type hello", layout_hash="abc123")
        record_step("press enter")
        result = stop_recording()
        assert result["steps"] == 3

    def test_steps_flushed_to_db(self):
        import nexus.mind.db as db
        from nexus.mind.workflows import start_recording, record_step, stop_recording
        start_recording("Test")
        record_step("click Compose")
        record_step("type hello", layout_hash="abc123")
        stop_recording()
        steps = db.steps_for_workflow("test")
        assert len(steps) == 2
        assert steps[0]["action"] == "click Compose"
        assert steps[1]["expected_hash"] == "abc123"

    def test_record_step_noop_when_not_recording(self):
        from nexus.mind.workflows import record_step
        # Should not raise
        record_step("click Save")


# ===========================================================================
# Storage API
# ===========================================================================

class TestStorageAPI:

    def setup_method(self):
        self._tmpdir = _reset_db()
        _reset_recording()

    def teardown_method(self):
        _teardown_db(self._tmpdir)
        _reset_recording()

    def test_list_empty(self):
        from nexus.mind.workflows import list_workflows
        assert list_workflows() == []

    def test_list_workflows(self):
        from nexus.mind.workflows import start_recording, stop_recording, list_workflows
        start_recording("Flow A")
        stop_recording()
        start_recording("Flow B")
        stop_recording()
        wfs = list_workflows()
        assert len(wfs) == 2

    def test_get_workflow_with_steps(self):
        from nexus.mind.workflows import start_recording, record_step, stop_recording, get_workflow
        start_recording("MyFlow")
        record_step("click Save")
        record_step("press enter")
        stop_recording()
        wf = get_workflow("myflow")
        assert wf is not None
        assert wf["name"] == "MyFlow"
        assert len(wf["steps"]) == 2

    def test_get_nonexistent(self):
        from nexus.mind.workflows import get_workflow
        assert get_workflow("nope") is None

    def test_delete_workflow(self):
        from nexus.mind.workflows import start_recording, stop_recording, delete_workflow, get_workflow
        start_recording("Temp")
        stop_recording()
        assert delete_workflow("temp") is True
        assert get_workflow("temp") is None

    def test_delete_nonexistent(self):
        from nexus.mind.workflows import delete_workflow
        assert delete_workflow("nope") is False


# ===========================================================================
# Replay
# ===========================================================================

class TestReplay:

    def setup_method(self):
        self._tmpdir = _reset_db()
        _reset_recording()

    def teardown_method(self):
        _teardown_db(self._tmpdir)
        _reset_recording()

    @patch("nexus.act.resolve.do")
    def test_replay_success(self, mock_do):
        from nexus.mind.workflows import start_recording, record_step, stop_recording, replay_workflow
        start_recording("Flow")
        record_step("click A")
        record_step("click B")
        stop_recording()

        mock_do.return_value = {"ok": True}
        result = replay_workflow("flow")

        assert result["ok"] is True
        assert result["completed"] == 2
        assert result["total"] == 2
        assert len(result["steps"]) == 2
        assert mock_do.call_count == 2

    @patch("nexus.act.resolve.do")
    def test_replay_failure_at_step(self, mock_do):
        from nexus.mind.workflows import start_recording, record_step, stop_recording, replay_workflow
        start_recording("Flow")
        record_step("click A")
        record_step("click MISSING")
        record_step("click C")
        stop_recording()

        mock_do.side_effect = [
            {"ok": True},
            {"ok": False, "error": "not found"},
        ]
        result = replay_workflow("flow")

        assert result["ok"] is False
        assert result["completed"] == 1
        assert result["total"] == 3
        assert "Step 2 failed" in result["error"]

    def test_replay_nonexistent(self):
        from nexus.mind.workflows import replay_workflow
        result = replay_workflow("nope")
        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_replay_empty_workflow(self):
        import nexus.mind.db as db
        from nexus.mind.workflows import replay_workflow
        db.workflow_create("empty", "Empty")
        result = replay_workflow("empty")
        assert result["ok"] is False
        assert "no steps" in result["error"]

    @patch("nexus.act.resolve.do")
    def test_replay_updates_success_stats(self, mock_do):
        import nexus.mind.db as db
        from nexus.mind.workflows import start_recording, record_step, stop_recording, replay_workflow
        start_recording("Flow")
        record_step("click A")
        stop_recording()

        mock_do.return_value = {"ok": True}
        replay_workflow("flow")

        wf = db.workflow_get("flow")
        assert wf["success_count"] == 1

    @patch("nexus.act.resolve.do")
    def test_replay_updates_fail_stats(self, mock_do):
        import nexus.mind.db as db
        from nexus.mind.workflows import start_recording, record_step, stop_recording, replay_workflow
        start_recording("Flow")
        record_step("click MISSING")
        stop_recording()

        mock_do.return_value = {"ok": False, "error": "not found"}
        replay_workflow("flow")

        wf = db.workflow_get("flow")
        assert wf["fail_count"] == 1


# ===========================================================================
# Hook integration
# ===========================================================================

class TestWorkflowHook:

    def setup_method(self):
        self._tmpdir = _reset_db()
        _reset_recording()

    def teardown_method(self):
        _teardown_db(self._tmpdir)
        _reset_recording()

    def test_hook_records_during_recording(self):
        from nexus.hooks import _workflow_record_hook
        from nexus.mind.workflows import start_recording, stop_recording, is_recording
        start_recording("HookTest")
        assert is_recording() is True

        ctx = {
            "action": "click Save",
            "result": {"ok": True},
            "after_hash": "abc123",
        }
        _workflow_record_hook(ctx)

        result = stop_recording()
        assert result["steps"] == 1

    def test_hook_noop_when_not_recording(self):
        from nexus.hooks import _workflow_record_hook
        ctx = {
            "action": "click Save",
            "result": {"ok": True},
            "after_hash": "abc123",
        }
        # Should not raise
        result = _workflow_record_hook(ctx)
        assert result == ctx

    def test_hook_skips_failed_actions(self):
        from nexus.hooks import _workflow_record_hook
        from nexus.mind.workflows import start_recording, stop_recording
        start_recording("HookTest")

        ctx = {
            "action": "click MISSING",
            "result": {"ok": False, "error": "not found"},
        }
        _workflow_record_hook(ctx)

        result = stop_recording()
        assert result["steps"] == 0


# ===========================================================================
# Resolve integration — workflow intents
# ===========================================================================

class TestWorkflowIntents:

    def setup_method(self):
        self._tmpdir = _reset_db()
        _reset_recording()

    def teardown_method(self):
        _teardown_db(self._tmpdir)
        _reset_recording()

    def test_record_start_intent(self):
        from nexus.act.resolve import do
        result = do("record start Test Flow")
        assert result["ok"] is True
        assert result["id"] == "test-flow"
        # Clean up
        from nexus.mind.workflows import stop_recording
        stop_recording()

    def test_record_stop_intent(self):
        from nexus.mind.workflows import start_recording
        start_recording("Test")
        from nexus.act.resolve import do
        result = do("record stop")
        assert result["ok"] is True

    def test_list_workflows_intent(self):
        from nexus.act.resolve import do
        result = do("list workflows")
        assert result["ok"] is True
        assert "text" in result

    def test_delete_workflow_intent(self):
        from nexus.mind.workflows import start_recording, stop_recording
        start_recording("ToDelete")
        stop_recording()
        from nexus.act.resolve import do
        result = do("delete workflow todelete")
        assert result["ok"] is True

    def test_delete_nonexistent_workflow_intent(self):
        from nexus.act.resolve import do
        result = do("delete workflow nope")
        assert result["ok"] is False

    def test_replay_intent(self):
        from nexus.mind.workflows import start_recording, record_step, stop_recording
        start_recording("ReplayMe")
        record_step("get clipboard")
        stop_recording()

        from nexus.act.resolve import do
        # replay calls do() for each step — "get clipboard" is safe and real
        result = do("replay replayme")
        assert result["ok"] is True
        assert result["completed"] == 1
