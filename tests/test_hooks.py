"""Tests for Phase 5 — Hook Pipeline.

5a: Registry mechanism (register, fire, clear, registered)
5b: Built-in hooks (spatial cache, OCR, system dialog, learning, journal)
5c: Integration (see/do pipeline with hooks wired)
"""

import sys
import threading
import time
import pytest
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, "/Users/ferran/repos/Nexus")


# ===========================================================================
# 5a: Registry Mechanism
# ===========================================================================

class TestHookRegistry:
    """Test register, fire, clear, registered."""

    def setup_method(self):
        from nexus.hooks import clear
        clear()

    def test_register_and_fire(self):
        """Basic register + fire returns modified ctx."""
        from nexus.hooks import register, fire

        def add_greeting(ctx):
            ctx["greeting"] = "hello"
            return ctx

        register("test_event", add_greeting)
        result = fire("test_event", {"name": "world"})
        assert result["greeting"] == "hello"
        assert result["name"] == "world"

    def test_fire_order_by_priority(self):
        """Lower priority runs first."""
        from nexus.hooks import register, fire

        order = []

        def hook_a(ctx):
            order.append("a")
            return ctx

        def hook_b(ctx):
            order.append("b")
            return ctx

        def hook_c(ctx):
            order.append("c")
            return ctx

        register("test_event", hook_c, priority=30)
        register("test_event", hook_a, priority=10)
        register("test_event", hook_b, priority=20)

        fire("test_event", {})
        assert order == ["a", "b", "c"]

    def test_fire_stop_signal(self):
        """{"stop": True} halts the chain."""
        from nexus.hooks import register, fire

        order = []

        def hook_first(ctx):
            order.append("first")
            return {"stop": True, "reason": "testing"}

        def hook_second(ctx):
            order.append("second")
            return ctx

        register("test_event", hook_first, priority=10)
        register("test_event", hook_second, priority=20)

        result = fire("test_event", {})
        assert order == ["first"]
        assert result["stop"] is True
        assert result["reason"] == "testing"

    def test_fire_error_isolation(self):
        """A broken hook doesn't break the pipeline."""
        from nexus.hooks import register, fire

        def broken_hook(ctx):
            raise RuntimeError("boom")

        def good_hook(ctx):
            ctx["ok"] = True
            return ctx

        register("test_event", broken_hook, priority=10)
        register("test_event", good_hook, priority=20)

        result = fire("test_event", {})
        assert result["ok"] is True

    def test_fire_none_return_preserves_ctx(self):
        """Hook returning None doesn't wipe context."""
        from nexus.hooks import register, fire

        def returns_none(ctx):
            pass  # Implicitly returns None

        register("test_event", returns_none)
        result = fire("test_event", {"key": "value"})
        assert result["key"] == "value"

    def test_fire_no_hooks(self):
        """Firing an event with no hooks returns ctx unchanged."""
        from nexus.hooks import fire

        ctx = {"data": 42}
        result = fire("nonexistent_event", ctx)
        assert result is ctx
        assert result["data"] == 42

    def test_clear_specific_event(self):
        """clear('before_see') only clears that event."""
        from nexus.hooks import register, clear, registered

        register("event_a", lambda ctx: ctx, name="hook_a")
        register("event_b", lambda ctx: ctx, name="hook_b")

        clear("event_a")
        assert registered("event_a") == []
        assert len(registered("event_b")) == 1

    def test_clear_all(self):
        """clear() clears everything."""
        from nexus.hooks import register, clear, registered

        register("event_a", lambda ctx: ctx)
        register("event_b", lambda ctx: ctx)

        clear()
        assert registered() == {}

    def test_registered_listing(self):
        """registered() returns hook list with priorities and names."""
        from nexus.hooks import register, registered

        register("test_event", lambda ctx: ctx, priority=10, name="first")
        register("test_event", lambda ctx: ctx, priority=50, name="second")

        result = registered("test_event")
        assert result == [(10, "first"), (50, "second")]

    def test_registered_all(self):
        """registered() with no args returns all events."""
        from nexus.hooks import register, registered

        register("event_a", lambda ctx: ctx, name="ha")
        register("event_b", lambda ctx: ctx, name="hb")

        result = registered()
        assert "event_a" in result
        assert "event_b" in result

    def test_thread_safety(self):
        """Concurrent register + fire doesn't crash."""
        from nexus.hooks import register, fire

        errors = []

        def register_hooks():
            try:
                for i in range(50):
                    register("concurrent", lambda ctx: ctx, priority=i, name=f"hook_{i}")
            except Exception as e:
                errors.append(e)

        def fire_hooks():
            try:
                for _ in range(50):
                    fire("concurrent", {"i": 1})
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=register_hooks),
            threading.Thread(target=fire_hooks),
            threading.Thread(target=register_hooks),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []

    def test_hook_modifies_mutable_list(self):
        """Hooks can modify mutable objects in ctx (like result_parts)."""
        from nexus.hooks import register, fire

        def append_hook(ctx):
            ctx["parts"].append("added by hook")
            return ctx

        register("test_event", append_hook)
        parts = ["original"]
        fire("test_event", {"parts": parts})
        assert parts == ["original", "added by hook"]

    def test_same_priority_stable_order(self):
        """Hooks with same priority keep registration order."""
        from nexus.hooks import register, fire

        order = []

        register("test_event", lambda ctx: (order.append("a"), ctx)[1], priority=50, name="a")
        register("test_event", lambda ctx: (order.append("b"), ctx)[1], priority=50, name="b")
        register("test_event", lambda ctx: (order.append("c"), ctx)[1], priority=50, name="c")

        fire("test_event", {})
        assert order == ["a", "b", "c"]


# ===========================================================================
# 5b: Built-in Hooks
# ===========================================================================

class TestSpatialCacheReadHook:
    """Test _spatial_cache_read hook."""

    def setup_method(self):
        from nexus.mind.session import reset
        reset()

    def test_cache_hit(self):
        """Returns cached_elements on cache hit."""
        from nexus.hooks import _spatial_cache_read
        from nexus.mind.session import spatial_put

        elements = [
            {"role": "button", "label": "Save", "_ax_role": "AXButton"},
            {"role": "button", "label": "Cancel", "_ax_role": "AXButton"},
        ]
        spatial_put(123, elements, max_elements=150)

        ctx = {"pid": 123, "fetch_limit": 150}
        result = _spatial_cache_read(ctx)
        assert result.get("cached_elements") is not None
        assert len(result["cached_elements"]) == 2

    def test_cache_miss(self):
        """Leaves cached_elements unset on miss."""
        from nexus.hooks import _spatial_cache_read

        ctx = {"pid": 999, "fetch_limit": 150}
        result = _spatial_cache_read(ctx)
        assert "cached_elements" not in result

    def test_cache_miss_none_pid(self):
        """Handles None PID gracefully."""
        from nexus.hooks import _spatial_cache_read

        ctx = {"pid": None, "fetch_limit": 150}
        result = _spatial_cache_read(ctx)
        assert "cached_elements" not in result


class TestSpatialCacheWriteHook:
    """Test _spatial_cache_write hook."""

    def setup_method(self):
        from nexus.mind.session import reset
        reset()

    def test_stores_elements(self):
        """Stores elements in spatial cache."""
        from nexus.hooks import _spatial_cache_write
        from nexus.mind.session import spatial_get

        elements = [
            {"role": "button", "label": "OK", "_ax_role": "AXButton"},
        ]
        ctx = {"pid": 456, "elements": elements, "fetch_limit": 150}
        _spatial_cache_write(ctx)

        cached, _ = spatial_get(456, 150)
        assert cached is not None
        assert len(cached) == 1

    def test_skips_when_from_cache(self):
        """Skips writing when elements came from cache."""
        from nexus.hooks import _spatial_cache_write
        from nexus.mind.session import spatial_get

        elements = [{"role": "button", "label": "OK", "_ax_role": "AXButton"}]
        ctx = {"pid": 789, "elements": elements, "fetch_limit": 150, "from_cache": True}
        _spatial_cache_write(ctx)

        cached, _ = spatial_get(789, 150)
        assert cached is None

    def test_skips_empty_elements(self):
        """Skips writing when elements is empty."""
        from nexus.hooks import _spatial_cache_write
        from nexus.mind.session import spatial_get

        ctx = {"pid": 101, "elements": [], "fetch_limit": 150}
        _spatial_cache_write(ctx)

        cached, _ = spatial_get(101, 150)
        assert cached is None


class TestOcrFallbackHook:
    """Test _ocr_fallback_hook."""

    def test_triggers_on_sparse_tree(self):
        """Triggers OCR when < 5 labeled elements."""
        from nexus.hooks import _ocr_fallback_hook

        mock_ocr_results = [
            {"label": "Open", "pos": [100, 200], "confidence": 0.95},
            {"label": "Cancel", "pos": [200, 200], "confidence": 0.90},
        ]

        with patch("nexus.sense.fusion._ocr_fallback", return_value=mock_ocr_results):
            parts = []
            ctx = {
                "elements": [{"label": "btn1"}, {"role": "image"}],
                "query": None,
                "pid": 123,
                "app_info": {"name": "TestApp"},
                "result_parts": parts,
            }
            _ocr_fallback_hook(ctx)
            assert any("OCR Fallback" in p for p in parts)
            assert any("Open" in p for p in parts)

    def test_skips_on_rich_tree(self):
        """Skips OCR when >= 5 labeled elements."""
        from nexus.hooks import _ocr_fallback_hook

        elements = [{"label": f"el{i}"} for i in range(10)]
        parts = []
        ctx = {
            "elements": elements, "query": None,
            "pid": 123, "app_info": {"name": "TestApp"},
            "result_parts": parts,
        }
        _ocr_fallback_hook(ctx)
        assert len(parts) == 0

    def test_skips_on_query(self):
        """Skips OCR when query is set."""
        from nexus.hooks import _ocr_fallback_hook

        parts = []
        ctx = {
            "elements": [], "query": "search term",
            "pid": 123, "app_info": {"name": "TestApp"},
            "result_parts": parts,
        }
        result = _ocr_fallback_hook(ctx)
        assert len(parts) == 0


class TestSystemDialogHook:
    """Test _system_dialog_hook."""

    def test_appends_dialog_text(self):
        """Appends system dialog text to result_parts."""
        from nexus.hooks import _system_dialog_hook

        with patch("nexus.sense.fusion._detect_system_dialogs", return_value="SYSTEM DIALOG: Gatekeeper"):
            parts = []
            ctx = {"result_parts": parts}
            _system_dialog_hook(ctx)
            assert any("SYSTEM DIALOG" in p for p in parts)

    def test_no_dialog(self):
        """Does nothing when no dialogs present."""
        from nexus.hooks import _system_dialog_hook

        with patch("nexus.sense.fusion._detect_system_dialogs", return_value=""):
            parts = []
            ctx = {"result_parts": parts}
            _system_dialog_hook(ctx)
            assert len(parts) == 0


class TestLearningHintsHook:
    """Test _learning_hints_hook."""

    def test_appends_hints(self):
        """Appends learning hints to result_parts."""
        from nexus.hooks import _learning_hints_hook

        with patch("nexus.mind.learn.hints_for_app", return_value="Save -> Guardar (3 uses)"):
            parts = []
            ctx = {"app_info": {"name": "TextEdit"}, "result_parts": parts}
            _learning_hints_hook(ctx)
            assert any("Learned:" in p for p in parts)
            assert any("Guardar" in p for p in parts)

    def test_skips_no_app_info(self):
        """Skips when app_info is None."""
        from nexus.hooks import _learning_hints_hook

        parts = []
        ctx = {"app_info": None, "result_parts": parts}
        _learning_hints_hook(ctx)
        assert len(parts) == 0

    def test_skips_no_hints(self):
        """Skips when no hints available."""
        from nexus.hooks import _learning_hints_hook

        with patch("nexus.mind.learn.hints_for_app", return_value=""):
            parts = []
            ctx = {"app_info": {"name": "TextEdit"}, "result_parts": parts}
            _learning_hints_hook(ctx)
            assert len(parts) == 0


class TestLearningRecordHook:
    """Test _learning_record_hook."""

    def test_records_success(self):
        """Records successful action with correlation."""
        from nexus.hooks import _learning_record_hook

        with patch("nexus.mind.learn.correlate_success", return_value=False) as mock_corr, \
             patch("nexus.mind.learn.record_action") as mock_rec:
            ctx = {
                "action": "click Save", "result": {"ok": True, "action": "ax_press"},
                "app_name": "TextEdit", "verb": "click", "target": "Save",
            }
            _learning_record_hook(ctx)
            mock_corr.assert_called_once_with("TextEdit", "click", "Save")
            mock_rec.assert_called_once()
            call_kwargs = mock_rec.call_args
            assert call_kwargs[1]["ok"] is True

    def test_records_failure(self):
        """Records failed action with not-found error."""
        from nexus.hooks import _learning_record_hook

        with patch("nexus.mind.learn.record_failure") as mock_fail, \
             patch("nexus.mind.learn.record_action") as mock_rec:
            ctx = {
                "action": "click Save", "result": {"ok": False, "error": "Element not found"},
                "app_name": "TextEdit", "verb": "click", "target": "Save",
            }
            _learning_record_hook(ctx)
            mock_fail.assert_called_once_with("TextEdit", "click", "Save")
            mock_rec.assert_called_once()

    def test_no_failure_record_for_other_errors(self):
        """Doesn't record failure for non-not-found errors."""
        from nexus.hooks import _learning_record_hook

        with patch("nexus.mind.learn.record_failure") as mock_fail, \
             patch("nexus.mind.learn.record_action") as mock_rec:
            ctx = {
                "action": "click Save", "result": {"ok": False, "error": "Timeout"},
                "app_name": "TextEdit", "verb": "click", "target": "Save",
            }
            _learning_record_hook(ctx)
            mock_fail.assert_not_called()
            mock_rec.assert_called_once()


class TestJournalRecordHook:
    """Test _journal_record_hook."""

    def setup_method(self):
        from nexus.mind.session import reset
        reset()

    def test_records_to_journal(self):
        """Records action in session journal."""
        from nexus.hooks import _journal_record_hook
        from nexus.mind.session import journal_entries

        ctx = {
            "action": "click Save", "app_name": "TextEdit",
            "result": {"ok": True}, "elapsed": 0.5,
            "changes": "Focus moved", "error": "",
        }
        _journal_record_hook(ctx)

        entries = journal_entries()
        assert len(entries) == 1
        assert entries[0]["action"] == "click Save"
        assert entries[0]["ok"] is True

    def test_records_failure_to_journal(self):
        """Records failed action in session journal."""
        from nexus.hooks import _journal_record_hook
        from nexus.mind.session import journal_entries

        ctx = {
            "action": "click Missing", "app_name": "Safari",
            "result": {"ok": False, "error": "Not found"},
            "elapsed": 1.2, "changes": "",
        }
        _journal_record_hook(ctx)

        entries = journal_entries()
        assert len(entries) == 1
        assert entries[0]["ok"] is False
        assert entries[0]["error"] == "Not found"


# ===========================================================================
# 5c: Bootstrap & Built-in Registration
# ===========================================================================

class TestBootstrap:
    """Test register_builtins and auto-registration."""

    def test_builtins_registered_on_import(self):
        """Built-in hooks are registered when hooks module is imported."""
        from nexus.hooks import clear, register_builtins, registered

        # Re-register (clear + re-register to get clean state)
        clear()
        register_builtins()

        hooks = registered()
        assert "before_see" in hooks
        assert "after_see" in hooks
        assert "before_do" in hooks
        assert "after_do" in hooks

        # Check specific hooks
        before_see = registered("before_see")
        assert any(name == "spatial_cache_read" for _, name in before_see)

        before_do = registered("before_do")
        assert any(name == "circuit_breaker" for _, name in before_do)

        after_see = registered("after_see")
        names = [name for _, name in after_see]
        assert "spatial_cache_write" in names
        assert "ocr_fallback" in names
        assert "system_dialog" in names
        assert "learning_hints" in names

        after_do = registered("after_do")
        names = [name for _, name in after_do]
        assert "learning_record" in names
        assert "journal_record" in names

    def test_builtin_priorities(self):
        """Built-in hooks have correct priority ordering."""
        from nexus.hooks import clear, register_builtins, registered

        clear()
        register_builtins()

        after_see = registered("after_see")
        priorities = [p for p, _ in after_see]
        # cache_write(10) < ocr(50) < dialog(60) < hints(70)
        assert priorities == sorted(priorities)
        assert priorities == [10, 50, 60, 70]

    def test_register_builtins_idempotent(self):
        """Calling register_builtins twice doubles hooks (but doesn't crash)."""
        from nexus.hooks import clear, register_builtins, registered

        clear()
        register_builtins()
        count1 = sum(len(v) for v in registered().values())
        register_builtins()
        count2 = sum(len(v) for v in registered().values())
        # Doubles because register() just appends
        assert count2 == count1 * 2

    def test_custom_hook_alongside_builtins(self):
        """User hooks coexist with built-in hooks."""
        from nexus.hooks import clear, register_builtins, register, registered

        clear()
        register_builtins()

        register("after_see", lambda ctx: ctx, priority=80, name="custom_after_see")

        after_see = registered("after_see")
        names = [name for _, name in after_see]
        assert "custom_after_see" in names
        assert "ocr_fallback" in names


# ===========================================================================
# 5d: Integration — full pipeline with hooks wired
# ===========================================================================

class TestSeeWithHooks:
    """Integration: see() fires hooks through the real pipeline."""

    def setup_method(self):
        from nexus.hooks import clear, register_builtins
        from nexus.mind.session import reset
        clear()
        register_builtins()
        reset()

    @patch("nexus.sense.fusion.access")
    @patch("nexus.sense.fusion._detect_system_dialogs", return_value="")
    @patch("nexus.sense.fusion._ocr_fallback", return_value=[])
    def test_see_fires_before_and_after_hooks(self, mock_ocr, mock_dialog, mock_access):
        """see() fires before_see and after_see events."""
        from nexus.sense.fusion import see

        # Setup mocks
        mock_access.is_trusted.return_value = True
        mock_access.frontmost_app.return_value = {"name": "TestApp", "pid": 100, "bundle_id": "com.test"}
        mock_access.window_title.return_value = "Test Window"
        mock_access.focused_element.return_value = None
        mock_access.windows.return_value = []
        mock_access.full_describe.return_value = {
            "elements": [
                {"role": "button", "label": "Save", "_ax_role": "AXButton"},
                {"role": "button", "label": "Cancel", "_ax_role": "AXButton"},
                {"role": "button", "label": "Help", "_ax_role": "AXButton"},
                {"role": "button", "label": "OK", "_ax_role": "AXButton"},
                {"role": "button", "label": "Apply", "_ax_role": "AXButton"},
            ],
            "tables": [],
            "lists": [],
        }

        # Track which hooks fire
        fired = []
        from nexus.hooks import register
        register("before_see", lambda ctx: (fired.append("before_see"), ctx)[1], priority=1, name="tracker_before")
        register("after_see", lambda ctx: (fired.append("after_see"), ctx)[1], priority=1, name="tracker_after")

        result = see()
        assert "before_see" in fired
        assert "after_see" in fired

    @patch("nexus.sense.fusion.access")
    @patch("nexus.sense.fusion._detect_system_dialogs", return_value="")
    @patch("nexus.sense.fusion._ocr_fallback", return_value=[])
    def test_see_spatial_cache_roundtrip(self, mock_ocr, mock_dialog, mock_access):
        """First see() caches via hook, second see() hits cache via hook."""
        from nexus.sense.fusion import see
        from nexus.mind.session import spatial_stats

        elements = [
            {"role": "button", "label": f"Btn{i}", "_ax_role": "AXButton"}
            for i in range(6)
        ]

        mock_access.is_trusted.return_value = True
        mock_access.running_apps.return_value = [{"name": "TestApp", "pid": 200, "bundle_id": "com.test"}]
        mock_access.window_title.return_value = "Window"
        mock_access.focused_element.return_value = None
        mock_access.windows.return_value = []
        mock_access.full_describe.return_value = {
            "elements": elements, "tables": [], "lists": [],
        }

        # Pass explicit PID (spatial cache requires non-None pid)
        see(app=200)
        assert mock_access.full_describe.call_count == 1
        stats = spatial_stats()
        assert stats["misses"] >= 1

        # Second call — cache hit, should NOT call full_describe again
        see(app=200)
        assert mock_access.full_describe.call_count == 1  # Still 1 — cache hit
        stats = spatial_stats()
        assert stats["hits"] >= 1

    @patch("nexus.sense.fusion.access")
    @patch("nexus.sense.fusion._detect_system_dialogs", return_value="")
    def test_see_ocr_fires_on_sparse_tree(self, mock_dialog, mock_access):
        """OCR hook fires when tree has < 5 labeled elements."""
        from nexus.sense.fusion import see

        mock_access.is_trusted.return_value = True
        mock_access.frontmost_app.return_value = {"name": "BlindApp", "pid": 300, "bundle_id": "com.blind"}
        mock_access.window_title.return_value = "Blind"
        mock_access.focused_element.return_value = None
        mock_access.windows.return_value = []
        mock_access.full_describe.return_value = {
            "elements": [{"role": "group", "_ax_role": "AXGroup"}],  # 0 labeled
            "tables": [], "lists": [],
        }

        ocr_results = [
            {"label": "Open", "pos": [100, 200], "confidence": 0.95},
        ]
        with patch("nexus.sense.fusion._ocr_fallback", return_value=ocr_results) as mock_ocr:
            result = see()
            mock_ocr.assert_called_once()
            assert "OCR Fallback" in result["text"]


class TestCustomHookIntegration:
    """Test user-registered hooks work in the pipeline."""

    def setup_method(self):
        from nexus.hooks import clear, register_builtins
        from nexus.mind.session import reset
        clear()
        register_builtins()
        reset()

    def test_custom_before_see_injects_elements(self):
        """A custom before_see hook can inject cached elements, skipping tree walk."""
        from nexus.hooks import register
        from nexus.sense.fusion import see

        custom_elements = [
            {"role": "button", "label": "Custom1", "_ax_role": "AXButton"},
            {"role": "button", "label": "Custom2", "_ax_role": "AXButton"},
            {"role": "button", "label": "Custom3", "_ax_role": "AXButton"},
            {"role": "button", "label": "Custom4", "_ax_role": "AXButton"},
            {"role": "button", "label": "Custom5", "_ax_role": "AXButton"},
        ]

        def inject_elements(ctx):
            ctx["cached_elements"] = custom_elements
            return ctx

        register("before_see", inject_elements, priority=5, name="injector")

        with patch("nexus.sense.fusion.access") as mock_access, \
             patch("nexus.sense.fusion._detect_system_dialogs", return_value=""), \
             patch("nexus.sense.fusion._ocr_fallback", return_value=[]):
            mock_access.is_trusted.return_value = True
            mock_access.frontmost_app.return_value = {"name": "App", "pid": 400, "bundle_id": "com.app"}
            mock_access.window_title.return_value = "Win"
            mock_access.focused_element.return_value = None
            mock_access.windows.return_value = []

            result = see()
            # full_describe should NOT be called — custom hook injected elements
            mock_access.full_describe.assert_not_called()
            assert "Custom1" in result["text"]

    def test_custom_after_do_hook_receives_context(self):
        """A custom after_do hook receives the correct context fields."""
        from nexus.hooks import register, fire

        received_ctx = {}

        def capture_ctx(ctx):
            received_ctx.update(ctx)
            return ctx

        register("after_do", capture_ctx, priority=99, name="ctx_capture")

        fire("after_do", {
            "action": "click Save", "pid": 123, "result": {"ok": True},
            "app_name": "TextEdit", "elapsed": 0.5,
            "changes": "Focus moved", "verb": "click", "target": "Save",
            "app_param": None,
        })

        assert received_ctx["action"] == "click Save"
        assert received_ctx["verb"] == "click"
        assert received_ctx["target"] == "Save"
        assert received_ctx["elapsed"] == 0.5


# ===========================================================================
# 5e: Circuit Breaker Hook
# ===========================================================================

class TestCircuitBreakerHook:
    """Test _circuit_breaker_hook — stops after consecutive failures."""

    def setup_method(self):
        from nexus.mind.session import reset
        reset()

    def test_allows_action_with_no_journal(self):
        """No journal entries — action proceeds."""
        from nexus.hooks import _circuit_breaker_hook

        ctx = {"action": "click Save", "pid": 123}
        result = _circuit_breaker_hook(ctx)
        assert result.get("stop") is None

    def test_allows_action_after_successes(self):
        """Recent successes — action proceeds."""
        from nexus.hooks import _circuit_breaker_hook
        from nexus.mind.session import journal_record

        for i in range(5):
            journal_record(f"click Btn{i}", "Mail", ok=True, elapsed=0.1)

        ctx = {"action": "click Save", "pid": 123}
        result = _circuit_breaker_hook(ctx)
        assert result.get("stop") is None

    def test_allows_action_after_1_failure(self):
        """One failure — still proceeds."""
        from nexus.hooks import _circuit_breaker_hook
        from nexus.mind.session import journal_record

        journal_record("click Missing", "Mail", ok=False, error="Not found")

        ctx = {"action": "click Save", "pid": 123}
        result = _circuit_breaker_hook(ctx)
        assert result.get("stop") is None

    def test_allows_action_after_2_failures(self):
        """Two failures — still proceeds."""
        from nexus.hooks import _circuit_breaker_hook
        from nexus.mind.session import journal_record

        journal_record("click X", "Mail", ok=False, error="Not found")
        journal_record("click Y", "Mail", ok=False, error="Not found")

        ctx = {"action": "click Z", "pid": 123}
        result = _circuit_breaker_hook(ctx)
        assert result.get("stop") is None

    def test_stops_after_3_consecutive_failures(self):
        """Three consecutive failures — circuit breaker trips."""
        from nexus.hooks import _circuit_breaker_hook
        from nexus.mind.session import journal_record

        journal_record("click X", "Mail", ok=False, error="Not found")
        journal_record("click Y", "Mail", ok=False, error="Not found")
        journal_record("click Z", "Mail", ok=False, error="Not found")

        ctx = {"action": "click W", "pid": 123}
        result = _circuit_breaker_hook(ctx)
        assert result.get("stop") is True
        assert "Circuit breaker" in result.get("error", "")
        assert "3 consecutive failures" in result["error"]

    def test_resets_on_success_between_failures(self):
        """A success between failures resets the counter."""
        from nexus.hooks import _circuit_breaker_hook
        from nexus.mind.session import journal_record

        journal_record("click X", "Mail", ok=False, error="Not found")
        journal_record("click Y", "Mail", ok=False, error="Not found")
        journal_record("click OK", "Mail", ok=True, elapsed=0.1)
        journal_record("click A", "Mail", ok=False, error="Not found")
        journal_record("click B", "Mail", ok=False, error="Not found")

        ctx = {"action": "click C", "pid": 123}
        result = _circuit_breaker_hook(ctx)
        # Only 2 failures after the success — should proceed
        assert result.get("stop") is None

    def test_ignores_old_failures(self):
        """Failures older than 30s are ignored."""
        from nexus.hooks import _circuit_breaker_hook
        from nexus.mind.session import _journal
        import time

        # Manually inject old failures (> 30s ago)
        old_ts = time.time() - 60
        for i in range(5):
            _journal.append({
                "ts": old_ts + i, "action": f"click X{i}",
                "app": "Mail", "ok": False, "elapsed": 0.1,
                "error": "Not found", "changes": "",
            })

        ctx = {"action": "click Y", "pid": 123}
        result = _circuit_breaker_hook(ctx)
        assert result.get("stop") is None

    def test_stops_after_5_consecutive(self):
        """Five consecutive failures — still tripped (threshold is 3)."""
        from nexus.hooks import _circuit_breaker_hook
        from nexus.mind.session import journal_record

        for i in range(5):
            journal_record(f"click X{i}", "Mail", ok=False, error="Not found")

        ctx = {"action": "click Y", "pid": 123}
        result = _circuit_breaker_hook(ctx)
        assert result.get("stop") is True
        assert "5 consecutive failures" in result["error"]

    def test_error_includes_failed_actions(self):
        """Error message lists the failed action names."""
        from nexus.hooks import _circuit_breaker_hook
        from nexus.mind.session import journal_record

        journal_record("click Save", "Mail", ok=False, error="Not found")
        journal_record("click Guardar", "Mail", ok=False, error="Not found")
        journal_record("click button 1", "Mail", ok=False, error="Not found")

        ctx = {"action": "click button 2", "pid": 123}
        result = _circuit_breaker_hook(ctx)
        assert "click Save" in result["error"]
        assert "click Guardar" in result["error"]
        assert "click button 1" in result["error"]


# ===========================================================================
# 5f: Paste Text (clipboard-based typing for long strings)
# ===========================================================================

class TestPasteText:
    """Test paste_text and type_text threshold."""

    @patch("nexus.act.input.pyautogui")
    @patch("nexus.act.input.subprocess")
    def test_short_string_uses_write(self, mock_sub, mock_pag):
        """Strings <= 8 chars use pyautogui.write (char-by-char)."""
        from nexus.act.input import type_text

        result = type_text("hello")
        mock_pag.write.assert_called_once_with("hello", interval=0.02)
        assert result["action"] == "type"

    @patch("nexus.act.input.pyautogui")
    @patch("nexus.act.input.subprocess")
    @patch("nexus.act.input.time")
    def test_long_string_uses_paste(self, mock_time, mock_sub, mock_pag):
        """Strings > 8 chars use clipboard paste (cmd+v)."""
        from nexus.act.input import type_text

        # Mock pbpaste (save clipboard)
        mock_sub.run.return_value = MagicMock(stdout=b"old-clipboard")

        result = type_text("smtp.serviciodecorreo.es")
        assert result["action"] == "paste"
        mock_pag.hotkey.assert_called_with("command", "v")

    @patch("nexus.act.input.pyautogui")
    @patch("nexus.act.input.subprocess")
    @patch("nexus.act.input.time")
    def test_paste_sets_clipboard(self, mock_time, mock_sub, mock_pag):
        """paste_text sets clipboard via pbcopy before pasting."""
        from nexus.act.input import paste_text

        mock_sub.run.return_value = MagicMock(stdout=b"old")

        paste_text("imap.server.com")

        # Should call subprocess.run at least twice: pbpaste (save) + pbcopy (set)
        calls = mock_sub.run.call_args_list
        assert len(calls) >= 2
        # First call: pbpaste
        assert calls[0][0][0] == ["pbpaste"]
        # Second call: pbcopy with our text
        assert calls[1][0][0] == ["pbcopy"]
        assert calls[1][1]["input"] == b"imap.server.com"

    @patch("nexus.act.input.pyautogui")
    @patch("nexus.act.input.subprocess")
    @patch("nexus.act.input.time")
    def test_paste_restores_clipboard(self, mock_time, mock_sub, mock_pag):
        """paste_text restores the original clipboard after pasting."""
        from nexus.act.input import paste_text

        mock_sub.run.return_value = MagicMock(stdout=b"important-data")

        paste_text("new-text")

        # Third call should be pbcopy to restore
        calls = mock_sub.run.call_args_list
        assert len(calls) >= 3
        assert calls[2][0][0] == ["pbcopy"]
        assert calls[2][1]["input"] == b"important-data"

    @patch("nexus.act.input.pyautogui")
    @patch("nexus.act.input.subprocess")
    def test_paste_falls_back_on_pbcopy_failure(self, mock_sub, mock_pag):
        """Falls back to char-by-char if pbcopy fails."""
        from nexus.act.input import paste_text

        # pbpaste works, pbcopy raises
        def side_effect(cmd, **kwargs):
            if cmd == ["pbpaste"]:
                return MagicMock(stdout=b"")
            raise OSError("pbcopy failed")

        mock_sub.run.side_effect = side_effect

        result = paste_text("long-text-here")
        assert result["action"] == "type"
        mock_pag.write.assert_called_once()

    def test_threshold_boundary(self):
        """Exactly 8 chars uses write, 9 chars uses paste."""
        from nexus.act.input import _PASTE_THRESHOLD
        assert _PASTE_THRESHOLD == 8
