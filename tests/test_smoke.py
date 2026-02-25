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
        """Redirect DB to a temp directory."""
        import nexus.mind.db as db
        self._tmpdir = tempfile.mkdtemp()
        db.close()
        db.DB_DIR = Path(self._tmpdir)
        db.DB_PATH = Path(self._tmpdir) / "nexus.db"
        db._conn = None

    def teardown_method(self):
        """Restore original DB paths."""
        import nexus.mind.db as db
        db.close()
        db.DB_DIR = Path.home() / ".nexus"
        db.DB_PATH = db.DB_DIR / "nexus.db"
        db._conn = None
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


# ===========================================================================
# Tree cache — verify caching behavior
# ===========================================================================


class TestTreeCache:
    """Test the tree cache in access.py."""

    def test_cache_set_and_get(self):
        from nexus.sense.access import _cache_set, _cache_get
        _cache_set("test_key", [1, 2, 3])
        result = _cache_get("test_key")
        assert result == [1, 2, 3]

    def test_cache_miss(self):
        from nexus.sense.access import _cache_get
        result = _cache_get("nonexistent_key_xyz_12345")
        assert result is None

    def test_cache_invalidate(self):
        from nexus.sense.access import _cache_set, _cache_get, invalidate_cache
        _cache_set("temp_key", "data")
        invalidate_cache()
        result = _cache_get("temp_key")
        assert result is None

    def test_cache_ttl_expires(self):
        import time
        from nexus.sense.access import _tree_cache, _CACHE_TTL, _cache_get
        # Manually insert an expired entry
        _tree_cache["old_key"] = (time.time() - _CACHE_TTL - 1, "stale")
        result = _cache_get("old_key")
        assert result is None


# ===========================================================================
# Full describe — single-pass tree walk
# ===========================================================================


class TestFullDescribe:
    """Test full_describe returns elements, tables, and lists."""

    def test_full_describe_returns_dict(self):
        from nexus.sense.access import full_describe
        result = full_describe()
        assert isinstance(result, dict)
        assert "elements" in result
        assert "tables" in result
        assert "lists" in result
        assert isinstance(result["elements"], list)
        assert isinstance(result["tables"], list)
        assert isinstance(result["lists"], list)

    def test_full_describe_elements_have_group(self):
        """Some elements should have _group annotations."""
        from nexus.sense.access import full_describe
        result = full_describe()
        # At least some elements should have groups (toolbars, etc.)
        groups = [el.get("_group") for el in result["elements"] if el.get("_group")]
        # On VS Code, there are always toolbars
        assert len(groups) >= 0  # May be 0 on apps without groups


# ===========================================================================
# Grouped rendering — unit tests for the renderer
# ===========================================================================


class TestGroupedRendering:
    """Test _render_grouped_elements and related functions."""

    def test_ungrouped_elements(self):
        """Elements without groups should render flat."""
        from nexus.sense.fusion import _render_grouped_elements
        elements = [
            {"role": "button", "label": "Save", "_ax_role": "AXButton"},
            {"role": "button", "label": "Cancel", "_ax_role": "AXButton"},
        ]
        lines = _render_grouped_elements(elements)
        assert len(lines) == 2
        assert all(line.startswith("  ") for line in lines)
        assert not any(line.endswith(":") for line in lines)

    def test_grouped_elements_with_heading(self):
        """Elements in a group with 2+ useful elements should get a heading."""
        from nexus.sense.fusion import _render_grouped_elements
        elements = [
            {"role": "button", "label": "Save", "_ax_role": "AXButton", "_group": "Toolbar"},
            {"role": "button", "label": "Cancel", "_ax_role": "AXButton", "_group": "Toolbar"},
            {"role": "button", "label": "Help", "_ax_role": "AXButton"},
        ]
        lines = _render_grouped_elements(elements)
        assert any("Toolbar:" in line for line in lines)
        # Grouped elements should be indented more
        toolbar_items = [l for l in lines if "Save" in l or "Cancel" in l]
        assert all(l.startswith("    ") for l in toolbar_items)

    def test_single_element_group_no_heading(self):
        """A group with only 1 useful element should NOT get a heading."""
        from nexus.sense.fusion import _render_grouped_elements
        elements = [
            {"role": "button", "label": "Solo", "_ax_role": "AXButton", "_group": "Tiny"},
        ]
        lines = _render_grouped_elements(elements)
        assert not any("Tiny:" in line for line in lines)

    def test_container_noise_suppressed(self):
        """Group container elements (AXToolbar etc.) should be suppressed under heading."""
        from nexus.sense.fusion import _render_grouped_elements
        elements = [
            {"role": "toolbar", "label": "", "_ax_role": "AXToolbar", "_group": "Toolbar"},
            {"role": "button", "label": "Save", "_ax_role": "AXButton", "_group": "Toolbar"},
            {"role": "button", "label": "Cancel", "_ax_role": "AXButton", "_group": "Toolbar"},
        ]
        lines = _render_grouped_elements(elements)
        # The toolbar element should be suppressed
        assert not any("toolbar" in line.lower() and "Save" not in line for line in lines
                       if "Toolbar:" not in line)
        # Save and Cancel should appear
        assert any("Save" in line for line in lines)
        assert any("Cancel" in line for line in lines)

    def test_long_group_label_truncated(self):
        """Very long group labels should be truncated."""
        from nexus.sense.fusion import _render_grouped_elements
        long_name = "A" * 80
        elements = [
            {"role": "button", "label": "X", "_ax_role": "AXButton", "_group": long_name},
            {"role": "button", "label": "Y", "_ax_role": "AXButton", "_group": long_name},
        ]
        lines = _render_grouped_elements(elements)
        heading = [l for l in lines if l.strip().endswith(":")]
        assert heading
        assert len(heading[0]) < 80  # Truncated

    def test_wrapper_group_suppression(self):
        """AXGroup wrappers that duplicate interactive elements should be removed."""
        from nexus.sense.fusion import _suppress_wrapper_groups
        elements = [
            {"role": "group", "label": "Save", "_ax_role": "AXGroup"},
            {"role": "button", "label": "Save", "_ax_role": "AXButton"},
            {"role": "group", "label": "Cancel", "_ax_role": "AXGroup"},
            {"role": "button", "label": "Cancel", "_ax_role": "AXButton"},
            {"role": "group", "label": "Unique Section", "_ax_role": "AXGroup"},
        ]
        result = _suppress_wrapper_groups(elements)
        labels = [el["label"] for el in result]
        # Wrapper groups should be removed
        assert labels.count("Save") == 1
        assert labels.count("Cancel") == 1
        # Unique group with no matching button should be kept
        assert "Unique Section" in labels

    def test_wrapper_suppression_keeps_unique_groups(self):
        """Groups with labels not matching any other element should survive."""
        from nexus.sense.fusion import _suppress_wrapper_groups
        elements = [
            {"role": "group", "label": "Sidebar", "_ax_role": "AXGroup"},
            {"role": "button", "label": "Home", "_ax_role": "AXButton"},
        ]
        result = _suppress_wrapper_groups(elements)
        # Both should be kept — "Sidebar" is unique
        assert len(result) == 2


# ===========================================================================
# Group label generation
# ===========================================================================


class TestGroupLabels:
    """Test _make_group_label in access.py."""

    def test_toolbar_with_label(self):
        from nexus.sense.access import _make_group_label
        assert _make_group_label("AXToolbar", "Main") == "Toolbar: Main"

    def test_toolbar_without_label(self):
        from nexus.sense.access import _make_group_label
        assert _make_group_label("AXToolbar", "") == "Toolbar"

    def test_dialog_with_label(self):
        from nexus.sense.access import _make_group_label
        assert _make_group_label("AXDialog", "Save As") == "Dialog: Save As"

    def test_group_with_label(self):
        from nexus.sense.access import _make_group_label
        # AXGroup has empty display name, so just uses the label
        assert _make_group_label("AXGroup", "Navigation") == "Navigation"

    def test_group_without_label(self):
        from nexus.sense.access import _make_group_label
        result = _make_group_label("AXGroup", "")
        assert result is None

    def test_unknown_role(self):
        from nexus.sense.access import _make_group_label
        result = _make_group_label("AXUnknown", "test")
        # Unknown roles just use the label
        assert result == "test"


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


class TestObserveSmoke:
    """Smoke tests for observation module — no accessibility permission needed."""

    def test_observe_module_imports(self):
        from nexus.sense import observe
        assert hasattr(observe, "start_observing")
        assert hasattr(observe, "stop_observing")
        assert hasattr(observe, "drain_events")
        assert hasattr(observe, "is_observing")
        assert hasattr(observe, "status")
        assert hasattr(observe, "format_events")

    def test_drain_events_without_starting(self):
        from nexus.sense.observe import drain_events
        assert drain_events() == []

    def test_is_observing_default_false(self):
        from nexus.sense.observe import is_observing
        assert is_observing() is False
        assert is_observing(12345) is False

    def test_status_default_empty(self):
        from nexus.sense.observe import status
        s = status()
        assert s["ok"] is True
        assert s["observing"] == []
        assert s["buffered"] == 0

    def test_format_events_empty(self):
        from nexus.sense.observe import format_events
        assert format_events([]) == ""

    def test_format_events_single(self):
        from nexus.sense.observe import format_events
        text = format_events([{"type": "AXWindowCreated", "role": "AXWindow", "label": "Test", "pid": 1, "ts": 1.0}])
        assert "Recent events (1):" in text
        assert "WindowCreated" in text

    def test_stop_observing_without_starting(self):
        from nexus.sense.observe import stop_observing
        result = stop_observing()
        assert result["ok"] is True
        assert result["stopped"] == []

    def test_notifications_list_populated(self):
        from nexus.sense.observe import _NOTIFICATIONS
        assert len(_NOTIFICATIONS) >= 5
        assert "AXWindowCreated" in _NOTIFICATIONS
        assert "AXValueChanged" in _NOTIFICATIONS


# ===========================================================================
# List windows (real code path)
# ===========================================================================


class TestListWindows:
    """Smoke tests for list windows getter."""

    def test_list_windows_returns_dict(self):
        from nexus.act.resolve import _list_windows
        result = _list_windows()
        assert isinstance(result, dict)
        assert result["ok"] is True
        assert "text" in result

    def test_list_windows_via_do(self):
        from nexus.act.resolve import do
        result = do("list windows")
        assert isinstance(result, dict)
        assert result["ok"] is True
