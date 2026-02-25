"""Tests for nexus/sense/plugins.py — perception plugin system.

Phase 6: Pluggable fallback stack for see().
"""

import sys
import time
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, "/Users/ferran/repos/Nexus")


# =========================================================================
# 6a: Registry
# =========================================================================

class TestRegistry:
    """Test plugin registration and discovery."""

    def setup_method(self):
        from nexus.sense.plugins import clear
        clear()

    def test_register_layer_adds_to_registry(self):
        from nexus.sense.plugins import register_layer, registered_layers
        register_layer("test", lambda pid, ctx: [], priority=10)
        assert ("test" in [n for _, n in registered_layers()])

    def test_priority_ordering(self):
        from nexus.sense.plugins import register_layer, registered_layers
        register_layer("low", lambda pid, ctx: [], priority=90)
        register_layer("high", lambda pid, ctx: [], priority=10)
        register_layer("mid", lambda pid, ctx: [], priority=50)
        layers = registered_layers()
        assert layers == [(10, "high"), (50, "mid"), (90, "low")]

    def test_clear_removes_all(self):
        from nexus.sense.plugins import register_layer, registered_layers, clear
        register_layer("a", lambda pid, ctx: [], priority=10)
        register_layer("b", lambda pid, ctx: [], priority=20)
        clear()
        assert registered_layers() == []

    def test_registered_layers_returns_copy(self):
        from nexus.sense.plugins import register_layer, registered_layers
        register_layer("x", lambda pid, ctx: [], priority=10)
        layers1 = registered_layers()
        layers2 = registered_layers()
        assert layers1 == layers2
        assert layers1 is not layers2

    def test_duplicate_names_allowed(self):
        from nexus.sense.plugins import register_layer, registered_layers
        register_layer("dup", lambda pid, ctx: [], priority=10)
        register_layer("dup", lambda pid, ctx: [], priority=20)
        names = [n for _, n in registered_layers()]
        assert names.count("dup") == 2

    def test_register_with_condition(self):
        from nexus.sense.plugins import register_layer, registered_layers
        register_layer("cond", lambda pid, ctx: [], priority=30, condition=lambda ctx: True)
        assert len(registered_layers()) == 1

    def test_default_priority(self):
        from nexus.sense.plugins import register_layer, registered_layers
        register_layer("default_pri", lambda pid, ctx: [])
        assert registered_layers() == [(50, "default_pri")]


# =========================================================================
# 6b: Pipeline execution
# =========================================================================

class TestPipeline:
    """Test perception pipeline execution."""

    def setup_method(self):
        from nexus.sense.plugins import clear
        clear()

    def test_empty_pipeline_returns_empty(self):
        from nexus.sense.plugins import run_pipeline
        elements, ctx = run_pipeline(123)
        assert elements == []
        assert ctx["pid"] == 123

    def test_single_layer_returns_elements(self):
        from nexus.sense.plugins import register_layer, run_pipeline
        def layer(pid, ctx):
            return [{"role": "button", "label": "Save", "pos": (100, 200)}]
        register_layer("test", layer, priority=10)
        elements, ctx = run_pipeline(123)
        assert len(elements) == 1
        assert elements[0]["label"] == "Save"

    def test_elements_tagged_with_source(self):
        from nexus.sense.plugins import register_layer, run_pipeline
        def layer(pid, ctx):
            return [{"role": "button", "label": "OK"}]
        register_layer("my_source", layer, priority=10)
        elements, _ = run_pipeline(123)
        assert elements[0]["source"] == "my_source"

    def test_handler_pre_tagged_source_preserved(self):
        from nexus.sense.plugins import register_layer, run_pipeline
        def layer(pid, ctx):
            return [{"role": "button", "label": "OK", "source": "custom"}]
        register_layer("default", layer, priority=10)
        elements, _ = run_pipeline(123)
        assert elements[0]["source"] == "custom"

    def test_multiple_layers_merge(self):
        from nexus.sense.plugins import register_layer, run_pipeline
        def layer_a(pid, ctx):
            return [{"role": "button", "label": "A"}]
        def layer_b(pid, ctx):
            return [{"role": "text", "label": "B"}]
        register_layer("a", layer_a, priority=10)
        register_layer("b", layer_b, priority=20)
        elements, _ = run_pipeline(123)
        assert len(elements) == 2
        assert elements[0]["label"] == "A"
        assert elements[1]["label"] == "B"

    def test_condition_false_skips_layer(self):
        from nexus.sense.plugins import register_layer, run_pipeline
        def layer(pid, ctx):
            return [{"role": "button", "label": "Skipped"}]
        register_layer("skip", layer, priority=10, condition=lambda ctx: False)
        elements, _ = run_pipeline(123)
        assert elements == []

    def test_condition_true_runs_layer(self):
        from nexus.sense.plugins import register_layer, run_pipeline
        def layer(pid, ctx):
            return [{"role": "button", "label": "Run"}]
        register_layer("run", layer, priority=10, condition=lambda ctx: True)
        elements, _ = run_pipeline(123)
        assert len(elements) == 1

    def test_condition_sees_prior_elements(self):
        from nexus.sense.plugins import register_layer, run_pipeline
        def layer_a(pid, ctx):
            return [{"role": "button", "label": "First"}]
        def condition_b(ctx):
            return len(ctx["elements"]) > 0
        def layer_b(pid, ctx):
            return [{"role": "text", "label": "Second"}]
        register_layer("a", layer_a, priority=10)
        register_layer("b", layer_b, priority=20, condition=condition_b)
        elements, _ = run_pipeline(123)
        assert len(elements) == 2

    def test_broken_handler_doesnt_break_pipeline(self):
        from nexus.sense.plugins import register_layer, run_pipeline
        def broken(pid, ctx):
            raise RuntimeError("boom")
        def good(pid, ctx):
            return [{"role": "button", "label": "OK"}]
        register_layer("broken", broken, priority=10)
        register_layer("good", good, priority=20)
        elements, _ = run_pipeline(123)
        assert len(elements) == 1
        assert elements[0]["label"] == "OK"

    def test_broken_condition_skips_layer(self):
        from nexus.sense.plugins import register_layer, run_pipeline
        def layer(pid, ctx):
            return [{"role": "button", "label": "Skip"}]
        register_layer("bad_cond", layer, priority=10,
                      condition=lambda ctx: 1 / 0)
        elements, _ = run_pipeline(123)
        assert elements == []

    def test_handler_returning_none_is_safe(self):
        from nexus.sense.plugins import register_layer, run_pipeline
        register_layer("none", lambda pid, ctx: None, priority=10)
        elements, _ = run_pipeline(123)
        assert elements == []

    def test_handler_returning_empty_is_safe(self):
        from nexus.sense.plugins import register_layer, run_pipeline
        register_layer("empty", lambda pid, ctx: [], priority=10)
        elements, _ = run_pipeline(123)
        assert elements == []

    def test_ctx_has_app_info(self):
        from nexus.sense.plugins import register_layer, run_pipeline
        captured = {}
        def layer(pid, ctx):
            captured.update(ctx)
            return []
        register_layer("spy", layer, priority=10)
        run_pipeline(123, app_info={"name": "Safari", "pid": 123})
        assert captured["app_info"]["name"] == "Safari"

    def test_ctx_has_bounds(self):
        from nexus.sense.plugins import register_layer, run_pipeline
        captured = {}
        def layer(pid, ctx):
            captured.update(ctx)
            return []
        register_layer("spy", layer, priority=10)
        run_pipeline(123, bounds=(0, 0, 800, 600))
        assert captured["bounds"] == (0, 0, 800, 600)

    def test_ctx_side_channel_tables(self):
        from nexus.sense.plugins import register_layer, run_pipeline
        def layer(pid, ctx):
            ctx["tables"] = [{"header": ["Name"], "rows": [["Alice"]]}]
            return [{"role": "table", "label": "People"}]
        register_layer("table_layer", layer, priority=10)
        _, ctx = run_pipeline(123)
        assert len(ctx["tables"]) == 1

    def test_pipeline_stores_in_cache(self):
        from nexus.sense.plugins import register_layer, run_pipeline, _cache_get
        def layer(pid, ctx):
            return [{"role": "button", "label": "Cached"}]
        register_layer("cache_test", layer, priority=10)
        run_pipeline(123)
        cached = _cache_get(123)
        assert cached is not None
        assert len(cached) == 1
        assert cached[0]["label"] == "Cached"


# =========================================================================
# 6c: Perception cache
# =========================================================================

class TestPerceptionCache:
    """Test perception cache put/get/invalidate."""

    def setup_method(self):
        from nexus.sense.plugins import clear
        clear()

    def test_put_and_get(self):
        from nexus.sense.plugins import _cache_put, _cache_get
        elements = [{"role": "button", "label": "OK"}]
        _cache_put(100, elements)
        result = _cache_get(100)
        assert result is not None
        assert len(result) == 1
        assert result[0]["label"] == "OK"

    def test_get_returns_copy(self):
        from nexus.sense.plugins import _cache_put, _cache_get
        elements = [{"role": "button", "label": "OK"}]
        _cache_put(100, elements)
        result = _cache_get(100)
        assert result is not elements

    def test_ttl_expiry(self):
        from nexus.sense.plugins import _cache_put, _cache_get, _perception_cache, _lock
        elements = [{"role": "button", "label": "Stale"}]
        _cache_put(100, elements)
        # Manually backdate timestamp
        with _lock:
            _perception_cache[100]["ts"] = time.time() - 10
        result = _cache_get(100)
        assert result is None

    def test_get_nonexistent_returns_none(self):
        from nexus.sense.plugins import _cache_get
        assert _cache_get(999) is None

    def test_get_none_pid_returns_none(self):
        from nexus.sense.plugins import _cache_get
        assert _cache_get(None) is None

    def test_put_none_pid_is_noop(self):
        from nexus.sense.plugins import _cache_put, _cache_get
        _cache_put(None, [{"role": "button"}])
        # Should not crash and nothing stored
        assert _cache_get(None) is None

    def test_invalidate_specific_pid(self):
        from nexus.sense.plugins import _cache_put, _cache_get, invalidate_cache
        _cache_put(100, [{"label": "A"}])
        _cache_put(200, [{"label": "B"}])
        invalidate_cache(100)
        assert _cache_get(100) is None
        assert _cache_get(200) is not None

    def test_invalidate_all(self):
        from nexus.sense.plugins import _cache_put, _cache_get, invalidate_cache
        _cache_put(100, [{"label": "A"}])
        _cache_put(200, [{"label": "B"}])
        invalidate_cache()
        assert _cache_get(100) is None
        assert _cache_get(200) is None

    def test_eviction_on_overflow(self):
        from nexus.sense.plugins import _cache_put, _cache_get, _MAX_CACHED_PIDS
        # Fill beyond capacity
        for i in range(_MAX_CACHED_PIDS + 5):
            _cache_put(i, [{"label": f"el_{i}"}])
            time.sleep(0.001)  # Ensure distinct timestamps
        # Latest entries should exist, some oldest evicted
        assert _cache_get(_MAX_CACHED_PIDS + 4) is not None

    def test_overwrite_existing(self):
        from nexus.sense.plugins import _cache_put, _cache_get
        _cache_put(100, [{"label": "old"}])
        _cache_put(100, [{"label": "new"}])
        result = _cache_get(100)
        assert result[0]["label"] == "new"


# =========================================================================
# 6d: perception_find
# =========================================================================

class TestPerceptionFind:
    """Test perception-aware element search."""

    def setup_method(self):
        from nexus.sense.plugins import clear
        clear()

    def _populate_cache(self, pid, elements):
        from nexus.sense.plugins import _cache_put
        _cache_put(pid, elements)

    def test_exact_label_match(self):
        from nexus.sense.plugins import perception_find
        self._populate_cache(100, [
            {"role": "button", "label": "Save", "source": "ax"},
            {"role": "button", "label": "Cancel", "source": "ax"},
        ])
        matches = perception_find("Save", 100)
        assert len(matches) >= 1
        assert matches[0]["label"] == "Save"

    def test_substring_match(self):
        from nexus.sense.plugins import perception_find
        self._populate_cache(100, [
            {"role": "button", "label": "Save As...", "source": "ax"},
        ])
        matches = perception_find("Save", 100)
        assert len(matches) == 1

    def test_case_insensitive(self):
        from nexus.sense.plugins import perception_find
        self._populate_cache(100, [
            {"role": "button", "label": "SAVE", "source": "ax"},
        ])
        matches = perception_find("save", 100)
        assert len(matches) == 1

    def test_ax_score_bonus(self):
        from nexus.sense.plugins import perception_find
        self._populate_cache(100, [
            {"role": "text (OCR)", "label": "Open", "source": "ocr"},
            {"role": "button", "label": "Open", "source": "ax"},
        ])
        matches = perception_find("Open", 100)
        assert len(matches) == 2
        # AX should be ranked first due to score bonus
        assert matches[0]["source"] == "ax"

    def test_finds_ocr_elements(self):
        from nexus.sense.plugins import perception_find
        self._populate_cache(100, [
            {"role": "text (OCR)", "label": "Install", "source": "ocr", "pos": (300, 400)},
        ])
        matches = perception_find("Install", 100)
        assert len(matches) == 1
        assert matches[0]["source"] == "ocr"

    def test_finds_template_elements(self):
        from nexus.sense.plugins import perception_find
        self._populate_cache(100, [
            {"role": "button (template)", "label": "Open", "source": "template", "pos": (400, 350)},
        ])
        matches = perception_find("Open", 100)
        assert len(matches) == 1
        assert matches[0]["source"] == "template"

    def test_no_match_returns_empty(self):
        from nexus.sense.plugins import perception_find
        self._populate_cache(100, [
            {"role": "button", "label": "Save", "source": "ax"},
        ])
        matches = perception_find("NonexistentLabel", 100)
        assert matches == []

    @patch("nexus.sense.access.find_elements", return_value=[{"role": "button", "label": "AX"}])
    def test_empty_cache_falls_back_to_ax(self, mock_find):
        from nexus.sense.plugins import perception_find
        matches = perception_find("AX", 100)
        assert len(matches) == 1
        mock_find.assert_called_once_with("AX", 100)

    def test_stale_cache_falls_back(self):
        from nexus.sense.plugins import perception_find, _cache_put, _perception_cache, _lock
        self._populate_cache(100, [{"role": "button", "label": "Stale"}])
        with _lock:
            _perception_cache[100]["ts"] = time.time() - 10
        with patch("nexus.sense.access.find_elements", return_value=[]) as mock:
            matches = perception_find("Stale", 100)
            mock.assert_called_once()

    def test_cross_source_search(self):
        from nexus.sense.plugins import perception_find
        self._populate_cache(100, [
            {"role": "button", "label": "Save", "source": "ax"},
            {"role": "text (OCR)", "label": "Open", "source": "ocr"},
            {"role": "button (template)", "label": "Cancel", "source": "template"},
        ])
        # Each source should be searchable
        assert len(perception_find("Save", 100)) == 1
        assert len(perception_find("Open", 100)) == 1
        assert len(perception_find("Cancel", 100)) == 1

    def test_value_match(self):
        from nexus.sense.plugins import perception_find
        self._populate_cache(100, [
            {"role": "text field", "label": "Email", "value": "user@example.com", "source": "ax"},
        ])
        matches = perception_find("user@example", 100)
        assert len(matches) == 1

    def test_role_label_combined_match(self):
        from nexus.sense.plugins import perception_find
        self._populate_cache(100, [
            {"role": "button", "label": "Save", "source": "ax"},
        ])
        matches = perception_find("button Save", 100)
        assert len(matches) == 1


# =========================================================================
# 6e: Built-in layers
# =========================================================================

class TestAxLayer:
    """Test the AX tree perception layer."""

    def setup_method(self):
        from nexus.sense.plugins import clear
        clear()

    @patch("nexus.sense.access.full_describe")
    def test_returns_elements_with_source_ax(self, mock_describe):
        from nexus.sense.plugins import _ax_layer
        mock_describe.return_value = {
            "elements": [
                {"role": "button", "label": "OK", "pos": (100, 200)},
                {"role": "text field", "label": "Name", "pos": (50, 100)},
            ],
            "tables": [],
            "lists": [],
        }
        ctx = {"pid": 123, "elements": [], "app_info": None, "bounds": None,
               "tables": [], "lists": [], "fetch_limit": 150}
        result = _ax_layer(123, ctx)
        assert len(result) == 2
        assert all(el["source"] == "ax" for el in result)

    @patch("nexus.sense.access.full_describe")
    def test_stores_tables_in_ctx(self, mock_describe):
        from nexus.sense.plugins import _ax_layer
        mock_describe.return_value = {
            "elements": [{"role": "table", "label": "People"}],
            "tables": [{"header": ["Name"], "rows": [["Alice"]]}],
            "lists": [],
        }
        ctx = {"pid": 123, "elements": [], "app_info": None, "bounds": None,
               "tables": [], "lists": [], "fetch_limit": 150}
        _ax_layer(123, ctx)
        assert len(ctx["tables"]) == 1

    @patch("nexus.sense.access.full_describe")
    def test_stores_lists_in_ctx(self, mock_describe):
        from nexus.sense.plugins import _ax_layer
        mock_describe.return_value = {
            "elements": [],
            "tables": [],
            "lists": [{"items": ["a", "b", "c"]}],
        }
        ctx = {"pid": 123, "elements": [], "app_info": None, "bounds": None,
               "tables": [], "lists": [], "fetch_limit": 150}
        _ax_layer(123, ctx)
        assert len(ctx["lists"]) == 1

    @patch("nexus.sense.access.full_describe")
    def test_uses_fetch_limit_from_ctx(self, mock_describe):
        from nexus.sense.plugins import _ax_layer
        mock_describe.return_value = {"elements": [], "tables": [], "lists": []}
        ctx = {"pid": 123, "elements": [], "app_info": None, "bounds": None,
               "tables": [], "lists": [], "fetch_limit": 200}
        _ax_layer(123, ctx)
        mock_describe.assert_called_once_with(123, max_elements=200)


class TestOcrLayer:
    """Test the OCR fallback perception layer."""

    def setup_method(self):
        from nexus.sense.plugins import clear
        clear()

    def test_ocr_condition_sparse(self):
        from nexus.sense.plugins import _ocr_condition
        ctx = {"elements": [
            {"role": "group", "label": ""},
            {"role": "button", "label": "OK"},
        ]}
        assert _ocr_condition(ctx) is True  # Only 1 labeled

    def test_ocr_condition_rich(self):
        from nexus.sense.plugins import _ocr_condition
        ctx = {"elements": [
            {"role": "button", "label": "A"},
            {"role": "button", "label": "B"},
            {"role": "button", "label": "C"},
            {"role": "button", "label": "D"},
            {"role": "button", "label": "E"},
        ]}
        assert _ocr_condition(ctx) is False  # 5 labeled >= threshold

    def test_ocr_condition_empty(self):
        from nexus.sense.plugins import _ocr_condition
        assert _ocr_condition({"elements": []}) is True

    @patch("nexus.sense.ocr.ocr_region")
    @patch("nexus.sense.ocr.ocr_to_elements")
    def test_ocr_layer_returns_elements(self, mock_to_el, mock_ocr):
        from nexus.sense.plugins import _ocr_layer
        mock_ocr.return_value = [{"text": "Open", "confidence": 0.95, "center": {"x": 300, "y": 400}}]
        mock_to_el.return_value = [{"role": "text (OCR)", "label": "Open", "source": "ocr", "pos": (300, 400)}]
        ctx = {"elements": [], "bounds": (0, 0, 800, 600)}
        result = _ocr_layer(123, ctx)
        assert len(result) == 1
        assert result[0]["label"] == "Open"

    def test_ocr_layer_no_bounds_returns_empty(self):
        from nexus.sense.plugins import _ocr_layer
        ctx = {"elements": [], "bounds": None}
        assert _ocr_layer(123, ctx) == []

    def test_ocr_layer_zero_size_returns_empty(self):
        from nexus.sense.plugins import _ocr_layer
        ctx = {"elements": [], "bounds": (0, 0, 0, 0)}
        assert _ocr_layer(123, ctx) == []


class TestTemplateLayer:
    """Test the dialog template perception layer."""

    def setup_method(self):
        from nexus.sense.plugins import clear
        clear()

    @patch("nexus.sense.system.detect_system_dialogs", return_value=[])
    def test_template_condition_no_dialogs(self, mock_detect):
        from nexus.sense.plugins import _template_condition
        assert _template_condition({}) is False

    @patch("nexus.sense.system.detect_system_dialogs")
    def test_template_condition_with_dialogs(self, mock_detect):
        from nexus.sense.plugins import _template_condition
        mock_detect.return_value = [{"process": "CoreServicesUIAgent", "bounds": {"x": 0, "y": 0, "w": 400, "h": 300}}]
        assert _template_condition({}) is True

    @patch("nexus.sense.system.detect_system_dialogs")
    @patch("nexus.sense.system.classify_dialog")
    @patch("nexus.sense.templates.match_template")
    @patch("nexus.sense.templates.resolve_button")
    def test_template_layer_creates_button_elements(self, mock_resolve, mock_match, mock_classify, mock_detect):
        from nexus.sense.plugins import _template_layer
        mock_detect.return_value = [{
            "process": "CoreServicesUIAgent",
            "bounds": {"x": 100, "y": 200, "w": 400, "h": 300},
        }]
        mock_match.return_value = ("gatekeeper_open", {
            "buttons": {
                "open": {"rel_x": 0.75, "rel_y": 0.85, "labels": ["Open", "Abrir"]},
                "cancel": {"rel_x": 0.55, "rel_y": 0.85, "labels": ["Cancel", "Cancelar"]},
            },
            "fields": {},
        })
        mock_resolve.side_effect = lambda tmpl, key, bounds: (
            (400, 455) if key == "open" else (320, 455)
        )
        ctx = {"elements": [], "bounds": None}
        result = _template_layer(123, ctx)
        assert len(result) == 2
        labels = {el["label"] for el in result}
        assert "Open" in labels
        assert "Cancel" in labels
        assert all(el["source"] == "template" for el in result)
        assert all(el["role"] == "button (template)" for el in result)

    @patch("nexus.sense.system.detect_system_dialogs", return_value=[])
    def test_template_layer_no_dialogs(self, mock_detect):
        from nexus.sense.plugins import _template_layer
        ctx = {"elements": []}
        result = _template_layer(123, ctx)
        assert result == []


# =========================================================================
# 6f: enrich_elements
# =========================================================================

class TestEnrichElements:
    """Test enriching AX elements with perception cache."""

    def setup_method(self):
        from nexus.sense.plugins import clear
        clear()

    def test_adds_ocr_elements(self):
        from nexus.sense.plugins import enrich_elements, _cache_put
        ax = [{"role": "button", "label": "Save", "source": "ax"}]
        _cache_put(100, [
            {"role": "button", "label": "Save", "source": "ax"},
            {"role": "text (OCR)", "label": "Install", "source": "ocr", "pos": (300, 400)},
        ])
        result = enrich_elements(ax, 100)
        assert len(result) == 2
        labels = {el["label"] for el in result}
        assert "Install" in labels

    def test_deduplicates_by_label(self):
        from nexus.sense.plugins import enrich_elements, _cache_put
        ax = [{"role": "button", "label": "Open", "source": "ax"}]
        _cache_put(100, [
            {"role": "button", "label": "Open", "source": "ax"},
            {"role": "text (OCR)", "label": "Open", "source": "ocr"},
        ])
        result = enrich_elements(ax, 100)
        # Should NOT add the OCR "Open" — label already in AX list
        assert len(result) == 1

    def test_no_cache_returns_original(self):
        from nexus.sense.plugins import enrich_elements
        ax = [{"role": "button", "label": "A"}]
        result = enrich_elements(ax, 999)
        assert result == ax

    def test_empty_ax_list(self):
        from nexus.sense.plugins import enrich_elements, _cache_put
        _cache_put(100, [
            {"role": "text (OCR)", "label": "Hello", "source": "ocr"},
        ])
        result = enrich_elements([], 100)
        assert len(result) == 1
        assert result[0]["label"] == "Hello"

    def test_skips_ax_source_from_cache(self):
        from nexus.sense.plugins import enrich_elements, _cache_put
        ax = [{"role": "button", "label": "A", "source": "ax"}]
        _cache_put(100, [
            {"role": "button", "label": "A", "source": "ax"},
            {"role": "button", "label": "B", "source": "ax"},  # AX from cache — skip
            {"role": "text (OCR)", "label": "C", "source": "ocr"},
        ])
        result = enrich_elements(ax, 100)
        labels = {el["label"] for el in result}
        # A from input, C from OCR, B skipped (source=ax)
        assert "A" in labels
        assert "C" in labels
        assert "B" not in labels

    def test_mixed_sources(self):
        from nexus.sense.plugins import enrich_elements, _cache_put
        ax = [{"role": "button", "label": "Save", "source": "ax"}]
        _cache_put(100, [
            {"role": "button", "label": "Save", "source": "ax"},
            {"role": "text (OCR)", "label": "Help", "source": "ocr"},
            {"role": "button (template)", "label": "Open", "source": "template"},
        ])
        result = enrich_elements(ax, 100)
        assert len(result) == 3
        sources = {el.get("source") for el in result}
        assert sources == {"ax", "ocr", "template"}


# =========================================================================
# 6g: _point_in_bounds helper
# =========================================================================

class TestPointInBounds:
    """Test the spatial helper."""

    def test_inside(self):
        from nexus.sense.plugins import _point_in_bounds
        assert _point_in_bounds((150, 250), {"x": 100, "y": 200, "w": 400, "h": 300}) is True

    def test_outside(self):
        from nexus.sense.plugins import _point_in_bounds
        assert _point_in_bounds((50, 50), {"x": 100, "y": 200, "w": 400, "h": 300}) is False

    def test_on_edge(self):
        from nexus.sense.plugins import _point_in_bounds
        assert _point_in_bounds((100, 200), {"x": 100, "y": 200, "w": 400, "h": 300}) is True

    def test_none_pos(self):
        from nexus.sense.plugins import _point_in_bounds
        assert _point_in_bounds(None, {"x": 0, "y": 0, "w": 100, "h": 100}) is False

    def test_none_bounds(self):
        from nexus.sense.plugins import _point_in_bounds
        assert _point_in_bounds((50, 50), None) is False


# =========================================================================
# 6h: register_builtins
# =========================================================================

class TestRegisterBuiltins:
    """Test built-in layer registration."""

    def setup_method(self):
        from nexus.sense.plugins import clear
        clear()

    def test_registers_three_layers(self):
        from nexus.sense.plugins import register_builtins, registered_layers
        register_builtins()
        layers = registered_layers()
        assert len(layers) == 3
        names = [n for _, n in layers]
        assert "ax" in names
        assert "ocr" in names
        assert "template" in names

    def test_priority_order(self):
        from nexus.sense.plugins import register_builtins, registered_layers
        register_builtins()
        layers = registered_layers()
        priorities = [p for p, _ in layers]
        assert priorities == sorted(priorities)

    def test_idempotent(self):
        from nexus.sense.plugins import register_builtins, registered_layers
        register_builtins()
        register_builtins()  # Should not double-register
        assert len(registered_layers()) == 3


# =========================================================================
# 6i: Integration
# =========================================================================

class TestIntegration:
    """Integration tests for the full perception pipeline."""

    def setup_method(self):
        from nexus.sense.plugins import clear
        clear()

    @patch("nexus.sense.access.full_describe")
    def test_full_pipeline_ax_only(self, mock_describe):
        from nexus.sense.plugins import register_builtins, run_pipeline
        mock_describe.return_value = {
            "elements": [
                {"role": "button", "label": "OK", "pos": (100, 200)},
                {"role": "button", "label": "Cancel", "pos": (200, 200)},
                {"role": "text field", "label": "Name", "pos": (50, 100)},
                {"role": "text field", "label": "Email", "pos": (50, 150)},
                {"role": "checkbox", "label": "Agree", "pos": (50, 200)},
            ],
            "tables": [],
            "lists": [],
        }
        register_builtins()
        elements, ctx = run_pipeline(123, app_info={"name": "Test", "pid": 123})
        # 5 labeled elements → OCR condition False → only AX elements
        assert len(elements) == 5
        assert all(el["source"] == "ax" for el in elements)

    @patch("nexus.sense.system.detect_system_dialogs", return_value=[])
    @patch("nexus.sense.ocr.ocr_to_elements")
    @patch("nexus.sense.ocr.ocr_region")
    @patch("nexus.sense.access.full_describe")
    def test_full_pipeline_ax_sparse_triggers_ocr(self, mock_describe, mock_ocr, mock_to_el, mock_sys):
        from nexus.sense.plugins import register_builtins, run_pipeline
        mock_describe.return_value = {
            "elements": [{"role": "group", "label": ""}],
            "tables": [],
            "lists": [],
        }
        mock_ocr.return_value = [{"text": "Docker", "confidence": 0.9, "center": {"x": 400, "y": 300}}]
        mock_to_el.return_value = [{"role": "text (OCR)", "label": "Docker", "source": "ocr", "pos": (400, 300)}]
        register_builtins()
        elements, _ = run_pipeline(123, bounds=(0, 0, 800, 600))
        # AX sparse (0 labeled) → OCR triggers
        sources = {el.get("source") for el in elements}
        assert "ocr" in sources

    @patch("nexus.sense.access.full_describe")
    def test_pipeline_then_find(self, mock_describe):
        from nexus.sense.plugins import register_builtins, run_pipeline, perception_find
        mock_describe.return_value = {
            "elements": [{"role": "button", "label": "Submit", "pos": (100, 200)}],
            "tables": [],
            "lists": [],
        }
        register_builtins()
        run_pipeline(123)
        # Now perception_find should find it in cache
        matches = perception_find("Submit", 123)
        assert len(matches) == 1
        assert matches[0]["label"] == "Submit"
