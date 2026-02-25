"""Tests for Phase 4 features — Remember (Session State).

4a: Session object (nexus/mind/session.py)
    - Spatial cache (get/put, TTL, dirty, eviction, ref stripping)
    - Layout hash (stability, sensitivity)
    - Action journal (record, recent format, maxlen)
    - Session metadata (tick, info, reset)
4b: Fusion integration (spatial cache in see/compact_state/snap)
4c: Server integration (journal in do() responses)
"""

import sys
import time
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, "/Users/ferran/repos/Nexus")


# ===========================================================================
# 4a: Spatial Cache
# ===========================================================================

class TestSpatialCache:
    """Test spatial_get/put, TTL, dirty marking, eviction."""

    def setup_method(self):
        from nexus.mind.session import reset
        reset()

    def test_put_and_get(self):
        """Basic store and retrieve."""
        from nexus.mind.session import spatial_put, spatial_get

        elements = [
            {"role": "button", "label": "Save", "_ax_role": "AXButton", "pos": [100, 50]},
            {"role": "button", "label": "Cancel", "_ax_role": "AXButton", "pos": [200, 50]},
        ]
        spatial_put(123, elements, max_elements=150)

        cached, hash_val = spatial_get(123, max_elements=150)
        assert cached is not None
        assert len(cached) == 2
        assert cached[0]["label"] == "Save"
        assert hash_val and len(hash_val) == 12

    def test_strips_ref_keeps_ax_role(self):
        """_ref is stripped (goes stale), _ax_role and _group are kept."""
        from nexus.mind.session import spatial_put, spatial_get

        elements = [
            {"role": "button", "label": "OK", "_ref": MagicMock(),
             "_ax_role": "AXButton", "_group": "Toolbar"},
        ]
        spatial_put(1, elements)

        cached, _ = spatial_get(1)
        assert "_ref" not in cached[0]
        assert cached[0]["_ax_role"] == "AXButton"
        assert cached[0]["_group"] == "Toolbar"

    def test_ttl_expiry(self):
        """Returns None after TTL expires."""
        from nexus.mind.session import spatial_put, spatial_get, _SPATIAL_TTL

        elements = [{"role": "button", "label": "OK"}]
        spatial_put(1, elements)

        # Should hit
        cached, _ = spatial_get(1)
        assert cached is not None

        # Expire it by manipulating timestamp
        from nexus.mind import session
        with session._spatial_lock:
            session._spatial_cache[1]["ts"] -= _SPATIAL_TTL + 1

        cached, _ = spatial_get(1)
        assert cached is None

    def test_dirty_miss(self):
        """Returns None when marked dirty."""
        from nexus.mind.session import spatial_put, spatial_get, mark_dirty

        elements = [{"role": "button", "label": "OK"}]
        spatial_put(1, elements)

        mark_dirty(1)

        cached, _ = spatial_get(1)
        assert cached is None

    def test_mark_dirty_single_pid(self):
        """Marks only the specified PID dirty."""
        from nexus.mind.session import spatial_put, spatial_get, mark_dirty

        spatial_put(1, [{"role": "button", "label": "A"}])
        spatial_put(2, [{"role": "button", "label": "B"}])

        mark_dirty(1)

        assert spatial_get(1)[0] is None
        assert spatial_get(2)[0] is not None

    def test_mark_dirty_all(self):
        """Marks all PIDs dirty when pid=None."""
        from nexus.mind.session import spatial_put, spatial_get, mark_dirty

        spatial_put(1, [{"role": "button", "label": "A"}])
        spatial_put(2, [{"role": "button", "label": "B"}])

        mark_dirty()  # All

        assert spatial_get(1)[0] is None
        assert spatial_get(2)[0] is None

    def test_max_elements_mismatch(self):
        """Returns None when max_elements doesn't match."""
        from nexus.mind.session import spatial_put, spatial_get

        elements = [{"role": "button", "label": "OK"}]
        spatial_put(1, elements, max_elements=150)

        # Different max_elements should miss
        cached, _ = spatial_get(1, max_elements=80)
        assert cached is None

        # Same max_elements should hit
        cached, _ = spatial_get(1, max_elements=150)
        assert cached is not None

    def test_eviction_at_capacity(self):
        """Oldest entry evicted when exceeding MAX_CACHED_PIDS."""
        from nexus.mind import session
        from nexus.mind.session import spatial_put, spatial_get

        # Fill exactly to capacity with staggered timestamps
        for i in range(session._MAX_CACHED_PIDS):
            spatial_put(i, [{"role": "button", "label": f"Btn{i}"}])
            with session._spatial_lock:
                session._spatial_cache[i]["ts"] = time.time() + i * 0.01

        # All should be present
        with session._spatial_lock:
            assert len(session._spatial_cache) == session._MAX_CACHED_PIDS

        # Add one more — should evict the oldest (pid=0, lowest ts)
        spatial_put(999, [{"role": "button", "label": "New"}])

        with session._spatial_lock:
            assert len(session._spatial_cache) <= session._MAX_CACHED_PIDS
            assert 0 not in session._spatial_cache  # Oldest evicted
            assert 999 in session._spatial_cache     # New one present

    def test_none_pid_returns_none(self):
        """spatial_get(None) returns (None, None)."""
        from nexus.mind.session import spatial_get
        assert spatial_get(None) == (None, None)

    def test_put_none_pid_noop(self):
        """spatial_put(None, ...) returns empty string."""
        from nexus.mind.session import spatial_put
        assert spatial_put(None, [{"role": "button", "label": "OK"}]) == ""

    def test_put_empty_elements_noop(self):
        """spatial_put with empty list returns empty string."""
        from nexus.mind.session import spatial_put
        assert spatial_put(1, []) == ""

    def test_spatial_stats(self):
        """Stats track hits and misses."""
        from nexus.mind.session import spatial_put, spatial_get, spatial_stats

        spatial_get(999)  # miss
        spatial_put(1, [{"role": "button", "label": "OK"}])
        spatial_get(1)    # hit
        spatial_get(2)    # miss

        stats = spatial_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 2
        assert stats["cached_pids"] == 1


# ===========================================================================
# Layout Hash
# ===========================================================================

class TestLayoutHash:
    """Test compute_layout_hash stability and sensitivity."""

    def test_stable_for_same_elements(self):
        """Same elements produce same hash."""
        from nexus.mind.session import compute_layout_hash

        elements = [
            {"_ax_role": "AXButton", "label": "Save"},
            {"_ax_role": "AXButton", "label": "Cancel"},
        ]
        h1 = compute_layout_hash(elements)
        h2 = compute_layout_hash(elements)
        assert h1 == h2
        assert len(h1) == 12

    def test_order_independent(self):
        """Hash is order-independent (sorted internally)."""
        from nexus.mind.session import compute_layout_hash

        e1 = [{"_ax_role": "AXButton", "label": "Save"}, {"_ax_role": "AXButton", "label": "Cancel"}]
        e2 = [{"_ax_role": "AXButton", "label": "Cancel"}, {"_ax_role": "AXButton", "label": "Save"}]
        assert compute_layout_hash(e1) == compute_layout_hash(e2)

    def test_changes_on_add(self):
        """Adding an element changes the hash."""
        from nexus.mind.session import compute_layout_hash

        base = [{"_ax_role": "AXButton", "label": "Save"}]
        extended = base + [{"_ax_role": "AXButton", "label": "Cancel"}]
        assert compute_layout_hash(base) != compute_layout_hash(extended)

    def test_changes_on_label(self):
        """Different label produces different hash."""
        from nexus.mind.session import compute_layout_hash

        e1 = [{"_ax_role": "AXButton", "label": "Save"}]
        e2 = [{"_ax_role": "AXButton", "label": "Save As"}]
        assert compute_layout_hash(e1) != compute_layout_hash(e2)

    def test_ignores_value(self):
        """Value changes don't affect hash."""
        from nexus.mind.session import compute_layout_hash

        e1 = [{"_ax_role": "AXTextField", "label": "Name", "value": "hello"}]
        e2 = [{"_ax_role": "AXTextField", "label": "Name", "value": "world"}]
        assert compute_layout_hash(e1) == compute_layout_hash(e2)

    def test_ignores_pos(self):
        """Position changes don't affect hash."""
        from nexus.mind.session import compute_layout_hash

        e1 = [{"_ax_role": "AXButton", "label": "OK", "pos": [100, 200]}]
        e2 = [{"_ax_role": "AXButton", "label": "OK", "pos": [300, 400]}]
        assert compute_layout_hash(e1) == compute_layout_hash(e2)

    def test_ignores_enabled(self):
        """Enabled state changes don't affect hash."""
        from nexus.mind.session import compute_layout_hash

        e1 = [{"_ax_role": "AXButton", "label": "OK", "enabled": True}]
        e2 = [{"_ax_role": "AXButton", "label": "OK", "enabled": False}]
        assert compute_layout_hash(e1) == compute_layout_hash(e2)

    def test_uses_ax_role_fallback_to_role(self):
        """Falls back to 'role' if '_ax_role' not present."""
        from nexus.mind.session import compute_layout_hash

        e1 = [{"_ax_role": "AXButton", "label": "OK"}]
        e2 = [{"role": "AXButton", "label": "OK"}]
        # _ax_role takes precedence but role is fallback
        assert compute_layout_hash(e1) == compute_layout_hash(e2)

    def test_empty_elements(self):
        """Empty list produces a valid hash."""
        from nexus.mind.session import compute_layout_hash
        h = compute_layout_hash([])
        assert isinstance(h, str)
        assert len(h) == 12


# ===========================================================================
# 4a: Action Journal
# ===========================================================================

class TestActionJournal:
    """Test journal recording and compact display."""

    def setup_method(self):
        from nexus.mind.session import reset
        reset()

    def test_record_basic(self):
        """Records an entry with all fields."""
        from nexus.mind.session import journal_record, journal_entries

        journal_record("click Save", "Safari", True, elapsed=0.3)

        entries = journal_entries()
        assert len(entries) == 1
        assert entries[0]["action"] == "click Save"
        assert entries[0]["app"] == "Safari"
        assert entries[0]["ok"] is True
        assert entries[0]["elapsed"] == 0.3

    def test_maxlen(self):
        """Oldest entries evicted at 50."""
        from nexus.mind.session import journal_record, journal_entries

        for i in range(60):
            journal_record(f"action {i}", "Test", True)

        entries = journal_entries()
        assert len(entries) == 50
        assert entries[0]["action"] == "action 10"  # First 10 evicted
        assert entries[-1]["action"] == "action 59"

    def test_recent_format(self):
        """Compact text format with relative time."""
        from nexus.mind.session import journal_record, journal_recent
        from nexus.mind import session

        journal_record("click File", "TextEdit", True)
        # Backdate it by 3 seconds
        session._journal[-1]["ts"] = time.time() - 3

        journal_record("click Save As", "TextEdit", True, changes="+ dialog Save As")

        result = journal_recent(n=2)
        assert "click File" in result
        assert "click Save As" in result
        assert "OK" in result
        assert "TextEdit" in result
        assert "ago" in result

    def test_recent_empty(self):
        """Returns empty string when journal is empty."""
        from nexus.mind.session import journal_recent
        assert journal_recent() == ""

    def test_recent_zero_n(self):
        """Returns empty string when n=0."""
        from nexus.mind.session import journal_record, journal_recent
        journal_record("test", "App", True)
        assert journal_recent(n=0) == ""

    def test_recent_with_error(self):
        """Failed actions show error hint."""
        from nexus.mind.session import journal_record, journal_recent

        journal_record("click Missing", "Safari", False, error="Element not found")

        result = journal_recent(n=1)
        assert "FAIL" in result
        assert "Element not found" in result

    def test_recent_with_changes(self):
        """Change summary included in output."""
        from nexus.mind.session import journal_record, journal_recent

        journal_record("click Save", "TextEdit", True, changes="Focus moved: button -> field")

        result = journal_recent(n=1)
        assert "Focus moved" in result

    def test_recent_truncates_long_action(self):
        """Actions over 30 chars get truncated."""
        from nexus.mind.session import journal_record, journal_recent

        long_action = "click the very long button label name here"
        journal_record(long_action, "App", True)

        result = journal_recent(n=1)
        assert "..." in result
        assert len(result.split(": ")[1].split(" -> ")[0]) <= 30

    def test_recent_truncates_long_error(self):
        """Errors over 30 chars get truncated."""
        from nexus.mind.session import journal_record, journal_recent

        long_error = "This is a very long error message that should be truncated"
        journal_record("click X", "App", False, error=long_error)

        result = journal_recent(n=1)
        assert "..." in result

    def test_age_minutes(self):
        """Shows minutes for old entries."""
        from nexus.mind.session import journal_record, journal_recent
        from nexus.mind import session

        journal_record("old action", "App", True)
        session._journal[-1]["ts"] = time.time() - 120  # 2 minutes ago

        result = journal_recent(n=1)
        assert "2m ago" in result


# ===========================================================================
# 4a: Session Metadata
# ===========================================================================

class TestSessionMetadata:
    """Test tick, session_info, reset."""

    def setup_method(self):
        from nexus.mind.session import reset
        reset()

    def test_tick_increments(self):
        """Request counter increases on tick."""
        from nexus.mind.session import tick, session_info

        tick()
        tick()
        tick()

        info = session_info()
        assert info["requests"] == 3

    def test_session_info_fields(self):
        """session_info returns all expected fields."""
        from nexus.mind.session import session_info

        info = session_info()
        assert "uptime" in info
        assert "requests" in info
        assert "spatial_cached_pids" in info
        assert "spatial_hits" in info
        assert "spatial_misses" in info
        assert "journal_entries" in info

    def test_reset_clears_everything(self):
        """reset() clears cache, journal, and counters."""
        from nexus.mind.session import (
            spatial_put, journal_record, tick, reset,
            spatial_stats, journal_entries, session_info,
        )

        spatial_put(1, [{"role": "button", "label": "OK"}])
        journal_record("test", "App", True)
        tick()

        reset()

        assert spatial_stats()["cached_pids"] == 0
        assert journal_entries() == []
        assert session_info()["requests"] == 0


# ===========================================================================
# 4b: Fusion integration (spatial cache in see/compact_state/snap)
# ===========================================================================

class TestFusionIntegration:
    """Test spatial cache integration into fusion.py."""

    def setup_method(self):
        from nexus.mind.session import reset
        reset()

    @patch("nexus.sense.fusion.access")
    @patch("nexus.sense.access.full_describe")
    @patch("nexus.sense.system.detect_system_dialogs", return_value=[])
    def test_see_populates_spatial_cache(self, mock_sys, mock_full, mock_access):
        """see() stores elements in spatial cache on miss."""
        from nexus.sense.fusion import see
        from nexus.mind.session import spatial_get

        mock_access.is_trusted.return_value = True
        mock_access.frontmost_app.return_value = {"name": "Safari", "pid": 123}
        mock_access.window_title.return_value = "Google"
        mock_access.focused_element.return_value = None
        mock_access.windows.return_value = []
        mock_full.return_value = {
            "elements": [
                {"role": "button", "label": "Save", "_ax_role": "AXButton",
                 "pos": [100, 50], "enabled": True},
            ],
            "tables": [],
            "lists": [],
        }

        see(app=123)

        # Should have populated the cache
        cached, hash_val = spatial_get(123, max_elements=max(80 * 2, 150))
        assert cached is not None
        assert len(cached) == 1
        assert cached[0]["label"] == "Save"

    @patch("nexus.sense.fusion.access")
    def test_see_uses_spatial_cache(self, mock_access):
        """see() returns cached elements on spatial cache hit."""
        from nexus.sense.fusion import see
        from nexus.mind.session import spatial_put

        mock_access.is_trusted.return_value = True
        mock_access.frontmost_app.return_value = {"name": "Safari", "pid": 123}
        mock_access.window_title.return_value = "Google"
        mock_access.focused_element.return_value = None
        mock_access.windows.return_value = []

        # Pre-populate spatial cache (fetch_limit = max(80*2, 150) = 160)
        elements = [
            {"role": "button", "label": "Cached", "_ax_role": "AXButton",
             "pos": [100, 50], "enabled": True},
        ]
        spatial_put(123, elements, max_elements=max(80 * 2, 150))

        result = see(app=123)

        assert "Cached" in result["text"]

    @patch("nexus.sense.fusion.access")
    def test_see_query_bypasses_cache(self, mock_access):
        """see(query=...) always does a fresh search, never uses spatial cache."""
        from nexus.sense.fusion import see
        from nexus.mind.session import spatial_put

        mock_access.is_trusted.return_value = True
        mock_access.frontmost_app.return_value = {"name": "Safari", "pid": 123}
        mock_access.window_title.return_value = "Google"
        mock_access.focused_element.return_value = None
        mock_access.windows.return_value = []
        mock_access.find_elements.return_value = [
            {"role": "button", "label": "Found", "pos": [100, 50]},
        ]

        # Pre-populate cache
        spatial_put(123, [{"role": "button", "label": "Cached"}], max_elements=150)

        result = see(app=123, query="button")

        mock_access.find_elements.assert_called_once()
        assert "Found" in result["text"]

    @patch("nexus.sense.fusion.access")
    def test_compact_state_uses_cache(self, mock_access):
        """compact_state() hits spatial cache populated by snap()."""
        from nexus.sense.fusion import compact_state
        from nexus.mind.session import spatial_put

        mock_access.frontmost_app.return_value = {"name": "Safari", "pid": 123}
        mock_access.window_title.return_value = "Google"
        mock_access.focused_element.return_value = None

        # Pre-populate cache (simulating snap() having run)
        elements = [
            {"role": "button", "label": "Save", "_ax_role": "AXButton",
             "pos": [100, 50], "enabled": True},
        ]
        spatial_put(123, elements)

        result = compact_state()

        # describe_app should NOT have been called (cache hit)
        mock_access.describe_app.assert_not_called()
        assert "Save" in result

    @patch("nexus.sense.fusion.access")
    def test_snap_populates_cache(self, mock_access):
        """snap() populates spatial cache for subsequent compact_state()."""
        from nexus.sense.fusion import snap
        from nexus.mind.session import spatial_get

        mock_access.frontmost_app.return_value = {"name": "Safari", "pid": 123}
        mock_access.running_apps.return_value = [{"name": "Safari", "pid": 123}]
        mock_access.focused_element.return_value = None
        mock_access.windows.return_value = []
        mock_access.describe_app.return_value = [
            {"role": "button", "label": "SnapBtn", "_ax_role": "AXButton"},
        ]

        snap(pid=123)

        # Spatial cache should now contain the elements
        cached, _ = spatial_get(123)
        assert cached is not None
        assert cached[0]["label"] == "SnapBtn"


# ===========================================================================
# 4c: Observer dirty marking integration
# ===========================================================================

class TestObserverDirtyIntegration:
    """Test that observer events mark spatial cache dirty."""

    def setup_method(self):
        from nexus.mind.session import reset
        reset()

    def test_mark_dirty_invalidates_cache(self):
        """mark_dirty from observer makes spatial_get return None."""
        from nexus.mind.session import spatial_put, spatial_get, mark_dirty

        spatial_put(42, [{"role": "button", "label": "OK"}])
        assert spatial_get(42)[0] is not None

        # Simulate observer event
        mark_dirty(42)

        assert spatial_get(42)[0] is None

    def test_new_put_clears_dirty(self):
        """Putting new data after dirty clears the dirty flag."""
        from nexus.mind.session import spatial_put, spatial_get, mark_dirty

        spatial_put(42, [{"role": "button", "label": "Old"}])
        mark_dirty(42)
        assert spatial_get(42)[0] is None

        # Fresh put clears dirty
        spatial_put(42, [{"role": "button", "label": "New"}])
        cached, _ = spatial_get(42)
        assert cached is not None
        assert cached[0]["label"] == "New"
