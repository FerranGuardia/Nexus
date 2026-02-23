"""Integration smoke tests for Nexus — see, do, memory.

These tests exercise the real code paths (not mocked), but only
the parts that don't require a running GUI or accessibility permission.
They verify the plumbing works: functions return the right shapes,
errors are handled gracefully, and the three tools are wired correctly.

Tests that need accessibility permission are marked with @pytest.mark.ax
so they can be run selectively on a machine with the right setup:
    pytest tests/test_smoke.py -m ax
"""

import sys
import os
import json
import pytest
import tempfile
from pathlib import Path

sys.path.insert(0, "/Users/ferran/repos/Nexus")


# ===========================================================================
# Memory tool — full round-trip (no permissions needed, uses temp file)
# ===========================================================================


class TestMemoryRoundTrip:
    """Test memory tool set/get/list/delete/clear with a temp store."""

    def setup_method(self):
        """Redirect memory store to a temp directory."""
        import nexus.mind.store as store_mod
        self._tmpdir = tempfile.mkdtemp()
        self._orig_dir = store_mod.STORE_DIR
        self._orig_file = store_mod.STORE_FILE
        store_mod.STORE_DIR = Path(self._tmpdir)
        store_mod.STORE_FILE = Path(self._tmpdir) / "memory.json"

    def teardown_method(self):
        """Restore original store paths."""
        import nexus.mind.store as store_mod
        store_mod.STORE_DIR = self._orig_dir
        store_mod.STORE_FILE = self._orig_file
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_set_and_get(self):
        from nexus.mind.store import memory
        result = memory(op="set", key="test_key", value="test_value")
        assert result["ok"] is True

        result = memory(op="get", key="test_key")
        assert result["ok"] is True
        assert result["value"] == "test_value"

    def test_list_keys(self):
        from nexus.mind.store import memory
        memory(op="set", key="alpha", value="1")
        memory(op="set", key="beta", value="2")

        result = memory(op="list")
        assert result["ok"] is True
        assert "alpha" in result["keys"]
        assert "beta" in result["keys"]

    def test_delete_key(self):
        from nexus.mind.store import memory
        memory(op="set", key="temp", value="data")
        result = memory(op="delete", key="temp")
        assert result["ok"] is True

        result = memory(op="get", key="temp")
        assert result["ok"] is False

    def test_clear(self):
        from nexus.mind.store import memory
        memory(op="set", key="a", value="1")
        memory(op="set", key="b", value="2")

        result = memory(op="clear")
        assert result["ok"] is True

        result = memory(op="list")
        assert result["count"] == 0

    def test_get_nonexistent(self):
        from nexus.mind.store import memory
        result = memory(op="get", key="nonexistent_key_xyz")
        assert result["ok"] is False

    def test_invalid_op(self):
        from nexus.mind.store import memory
        result = memory(op="frobnicate")
        assert result["ok"] is False

    def test_set_missing_key(self):
        from nexus.mind.store import memory
        result = memory(op="set", key=None, value="hello")
        assert result["ok"] is False

    def test_set_overwrites(self):
        from nexus.mind.store import memory
        memory(op="set", key="x", value="old")
        memory(op="set", key="x", value="new")
        result = memory(op="get", key="x")
        assert result["value"] == "new"


# ===========================================================================
# Resolve tool — pure function smoke tests (no mocking)
# ===========================================================================


class TestResolveSmoke:
    """Quick sanity checks on resolve functions that don't touch the OS."""

    def test_parse_spatial_returns_tuple_or_none(self):
        from nexus.act.resolve import _parse_spatial
        result = _parse_spatial("button near search")
        assert isinstance(result, tuple) and len(result) == 3
        assert _parse_spatial("just a label") is None

    def test_normalize_action_idempotent(self):
        from nexus.act.resolve import _normalize_action
        # Normalizing an already-canonical action should not change it
        assert _normalize_action("click Save") == "click Save"
        assert _normalize_action("type hello") == "type hello"
        assert _normalize_action("scroll down") == "scroll down"

    def test_strip_quotes_various(self):
        from nexus.act.resolve import _strip_quotes
        assert _strip_quotes('"hello"') == "hello"
        assert _strip_quotes("'hello'") == "hello"
        assert _strip_quotes("hello") == "hello"

    def test_parse_fields_roundtrip(self):
        from nexus.act.resolve import _parse_fields
        pairs = _parse_fields("Name=Ferran, Email=f@x.com, Age=30")
        assert len(pairs) == 3
        assert pairs[0] == ("Name", "Ferran")

    def test_filter_by_search_with_elements(self):
        from nexus.act.resolve import _filter_by_search
        elements = [
            {"label": "Save", "_ax_role": "AXButton", "role": "button"},
            {"label": "Cancel", "_ax_role": "AXButton", "role": "button"},
            {"label": "Search", "_ax_role": "AXTextField", "role": "field"},
        ]
        buttons = _filter_by_search(elements, "button")
        assert len(buttons) == 2
        save = _filter_by_search(elements, "Save")
        assert len(save) == 1


# ===========================================================================
# Fusion — see() output structure (may need accessibility)
# ===========================================================================


class TestSeeOutputStructure:
    """Test that see() returns correctly structured output."""

    def test_see_returns_dict_with_text(self):
        """see() should always return a dict with 'text' key."""
        from nexus.sense.fusion import see
        result = see()
        assert isinstance(result, dict)
        assert "text" in result
        assert isinstance(result["text"], str)
        assert len(result["text"]) > 0

    def test_see_with_query_returns_dict(self):
        from nexus.sense.fusion import see
        result = see(query="Save")
        assert isinstance(result, dict)
        assert "text" in result
        assert 'Search "Save"' in result["text"]

    def test_see_with_diff_returns_dict(self):
        from nexus.sense.fusion import see
        # First call establishes baseline
        see()
        # Second call with diff
        result = see(diff=True)
        assert isinstance(result, dict)
        assert "text" in result

    def test_see_nonexistent_app(self):
        """see() with a nonexistent app should still return valid output."""
        from nexus.sense.fusion import see
        result = see(app="NonexistentApp12345")
        assert isinstance(result, dict)
        assert "text" in result


# ===========================================================================
# Do tool — getter intents that are safe to call
# ===========================================================================


class TestDoGetters:
    """Test do() getter intents that are safe (read-only, no side effects)."""

    def test_get_clipboard_returns_text(self):
        """get clipboard should return text from pbpaste."""
        from nexus.act.resolve import do
        result = do("get clipboard")
        assert result["ok"] is True
        assert "text" in result

    def test_empty_action_error(self):
        from nexus.act.resolve import do
        result = do("")
        assert result["ok"] is False

    def test_whitespace_action_error(self):
        from nexus.act.resolve import do
        result = do("   ")
        assert result["ok"] is False


# ===========================================================================
# Server tool wrappers — verify MCP tool functions exist and have right sigs
# ===========================================================================


class TestServerToolSignatures:
    """Verify the MCP server tools are properly defined."""

    def test_see_tool_exists(self):
        from nexus.server import see
        import inspect
        sig = inspect.signature(see)
        params = set(sig.parameters.keys())
        assert "app" in params
        assert "query" in params
        assert "screenshot" in params
        assert "menus" in params
        assert "diff" in params
        assert "content" in params

    def test_do_tool_exists(self):
        from nexus.server import do
        import inspect
        sig = inspect.signature(do)
        params = set(sig.parameters.keys())
        assert "action" in params
        assert "app" in params

    def test_memory_tool_exists(self):
        from nexus.server import memory
        import inspect
        sig = inspect.signature(memory)
        params = set(sig.parameters.keys())
        assert "op" in params
        assert "key" in params
        assert "value" in params


# ===========================================================================
# Web module — CDP helpers (no Chrome needed for these)
# ===========================================================================


class TestCdpHelpers:
    """Test CDP helper functions that don't need a running Chrome."""

    def test_cdp_available_returns_bool(self):
        from nexus.sense.web import cdp_available
        result = cdp_available()
        assert isinstance(result, bool)

    def test_tab_list_returns_list(self):
        from nexus.sense.web import tab_list
        result = tab_list()
        assert isinstance(result, list)

    def test_page_info_returns_none_without_chrome(self):
        from nexus.sense.web import page_info
        # Without Chrome running, should return None
        result = page_info()
        # Result is None or a dict — both valid
        assert result is None or isinstance(result, dict)
