"""Unit tests for nexus.state — shared state between MCP server and panel."""

import sys
import json
import time
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, "/Users/ferran/repos/Nexus")


@pytest.fixture(autouse=True)
def temp_state(tmp_path):
    """Redirect state file to a temp directory for each test."""
    state_dir = tmp_path / ".nexus"
    state_file = state_dir / "state.json"
    with patch("nexus.state.STATE_DIR", state_dir), \
         patch("nexus.state.STATE_FILE", state_file):
        yield state_file


class TestReadState:
    def test_empty_when_no_file(self, temp_state):
        from nexus.state import read_state
        assert read_state() == {}

    def test_reads_existing_state(self, temp_state):
        from nexus.state import read_state
        temp_state.parent.mkdir(parents=True, exist_ok=True)
        temp_state.write_text(json.dumps({"paused": True, "hint": "hello"}))
        state = read_state()
        assert state["paused"] is True
        assert state["hint"] == "hello"

    def test_handles_corrupt_json(self, temp_state):
        from nexus.state import read_state
        temp_state.parent.mkdir(parents=True, exist_ok=True)
        temp_state.write_text("not json {{{")
        assert read_state() == {}


class TestWriteState:
    def test_creates_file_and_dir(self, temp_state):
        from nexus.state import write_state
        write_state(action="click Save", status="running")
        assert temp_state.exists()
        data = json.loads(temp_state.read_text())
        assert data["action"] == "click Save"
        assert data["status"] == "running"
        assert "ts" in data

    def test_merges_fields(self, temp_state):
        from nexus.state import write_state, read_state
        write_state(action="click Save", status="running")
        write_state(status="done")
        state = read_state()
        assert state["action"] == "click Save"  # preserved
        assert state["status"] == "done"  # updated

    def test_updates_timestamp(self, temp_state):
        from nexus.state import write_state, read_state
        write_state(action="test")
        ts1 = read_state()["ts"]
        time.sleep(0.01)
        write_state(status="done")
        ts2 = read_state()["ts"]
        assert ts2 > ts1


class TestEmit:
    def test_writes_step(self, temp_state):
        from nexus.state import emit, read_state
        emit("Searching for 'Save'...")
        state = read_state()
        assert state["step"] == "Searching for 'Save'..."

    def test_preserves_other_fields(self, temp_state):
        from nexus.state import write_state, emit, read_state
        write_state(action="click Save", status="running")
        emit("Trying AXPress...")
        state = read_state()
        assert state["action"] == "click Save"
        assert state["status"] == "running"
        assert state["step"] == "Trying AXPress..."

    def test_never_raises(self, temp_state):
        """emit() should never raise, even with broken state."""
        from nexus.state import emit
        # Force a broken path
        with patch("nexus.state.STATE_DIR", Path("/nonexistent/path/xxx")):
            emit("this should not raise")  # Should silently fail


class TestStartAction:
    def test_sets_all_fields(self, temp_state):
        from nexus.state import start_action, read_state
        start_action("do", "click Save", app="Safari")
        state = read_state()
        assert state["tool"] == "do"
        assert state["action"] == "click Save"
        assert state["app"] == "Safari"
        assert state["status"] == "running"
        assert state["step"] == ""
        assert state["error"] == ""
        assert state["start_ts"] > 0

    def test_see_action(self, temp_state):
        from nexus.state import start_action, read_state
        start_action("see", "query=search", app="Chrome")
        state = read_state()
        assert state["tool"] == "see"
        assert state["action"] == "query=search"


class TestEndAction:
    def test_done_appends_log(self, temp_state):
        from nexus.state import start_action, end_action, read_state
        start_action("do", "click Save", app="Safari")
        time.sleep(0.01)
        end_action("done")
        state = read_state()
        assert state["status"] == "done"
        assert len(state["log"]) == 1
        entry = state["log"][0]
        assert entry["action"] == "click Save"
        assert entry["status"] == "done"
        assert entry["elapsed"] >= 0
        assert entry["error"] == ""

    def test_failed_with_error(self, temp_state):
        from nexus.state import start_action, end_action, read_state
        start_action("do", "click Submit")
        end_action("failed", error='Element "Submit" not found')
        state = read_state()
        assert state["status"] == "failed"
        assert len(state["log"]) == 1
        assert state["log"][0]["error"] == 'Element "Submit" not found'

    def test_clears_step(self, temp_state):
        from nexus.state import start_action, emit, end_action, read_state
        start_action("do", "click Save")
        emit("Trying AXPress...")
        end_action("done")
        state = read_state()
        assert state["step"] == ""

    def test_log_capped(self, temp_state):
        from nexus.state import start_action, end_action, read_state, _MAX_LOG
        for i in range(_MAX_LOG + 10):
            start_action("do", f"action {i}")
            end_action("done")
        state = read_state()
        assert len(state["log"]) == _MAX_LOG
        # Most recent should be the last one
        assert state["log"][-1]["action"] == f"action {_MAX_LOG + 9}"

    def test_elapsed_calculation(self, temp_state):
        from nexus.state import start_action, end_action, read_state
        start_action("do", "slow action")
        time.sleep(0.05)
        end_action("done")
        state = read_state()
        assert state["log"][0]["elapsed"] >= 0.04


class TestReadAndClearHint:
    def test_returns_none_when_no_hint(self, temp_state):
        from nexus.state import read_and_clear_hint
        assert read_and_clear_hint() is None

    def test_returns_none_for_empty_hint(self, temp_state):
        from nexus.state import write_state, read_and_clear_hint
        write_state(hint="", hint_ts=0)
        assert read_and_clear_hint() is None

    def test_returns_hint_and_clears(self, temp_state):
        from nexus.state import write_state, read_and_clear_hint, read_state
        write_state(hint="I clicked Save for you", hint_ts=time.time())
        hint = read_and_clear_hint()
        assert hint == "I clicked Save for you"
        # Hint should be cleared now
        state = read_state()
        assert state["hint"] == ""
        assert state["hint_ts"] == 0

    def test_second_read_returns_none(self, temp_state):
        from nexus.state import write_state, read_and_clear_hint
        write_state(hint="test hint", hint_ts=time.time())
        read_and_clear_hint()  # first read clears it
        assert read_and_clear_hint() is None


class TestClearState:
    def test_resets_to_defaults(self, temp_state):
        from nexus.state import write_state, clear_state, read_state
        write_state(paused=True, action="click X", hint="help")
        clear_state()
        state = read_state()
        assert state["paused"] is False
        assert state["action"] == ""
        assert state["hint"] == ""
        assert state["status"] == "idle"
        assert state["step"] == ""
        assert state["tool"] == ""
        assert state["log"] == []


class TestAtomicWrite:
    def test_no_tmp_file_left(self, temp_state):
        from nexus.state import write_state
        write_state(action="test")
        tmp = temp_state.with_suffix(".tmp")
        assert not tmp.exists()

    def test_concurrent_reads_safe(self, temp_state):
        """Write + immediate read should never see partial data."""
        from nexus.state import write_state, read_state
        for i in range(50):
            write_state(action=f"step {i}", status="running")
            state = read_state()
            assert "action" in state
            assert state["action"] == f"step {i}"


class TestFullPipeline:
    """Integration tests for the full start → emit → end flow."""

    def test_see_pipeline(self, temp_state):
        from nexus.state import start_action, emit, end_action, read_state
        start_action("see", "full tree", app="Safari")
        emit("Building accessibility tree...")
        state = read_state()
        assert state["step"] == "Building accessibility tree..."
        assert state["status"] == "running"
        end_action("done")
        state = read_state()
        assert state["status"] == "done"
        assert state["step"] == ""
        assert len(state["log"]) == 1

    def test_do_pipeline_success(self, temp_state):
        from nexus.state import start_action, emit, end_action, read_state
        start_action("do", "click Save", app="Safari")
        emit("Searching for 'Save'...")
        emit("Found, trying AXPress on [button] \"Save\"...")
        emit("Verifying changes...")
        end_action("done")
        state = read_state()
        assert state["status"] == "done"
        assert len(state["log"]) == 1
        assert state["log"][0]["status"] == "done"

    def test_do_pipeline_failure(self, temp_state):
        from nexus.state import start_action, emit, end_action, read_state
        start_action("do", "click Submit")
        emit("Searching for 'Submit'...")
        end_action("failed", error='Element "Submit" not found')
        state = read_state()
        assert state["status"] == "failed"
        assert state["log"][0]["error"] == 'Element "Submit" not found'

    def test_multiple_actions_build_log(self, temp_state):
        from nexus.state import start_action, end_action, read_state
        start_action("see", "full tree")
        end_action("done")
        start_action("do", "click Save")
        end_action("done")
        start_action("do", "type hello")
        end_action("done")
        state = read_state()
        assert len(state["log"]) == 3
        assert [e["action"] for e in state["log"]] == ["full tree", "click Save", "type hello"]
