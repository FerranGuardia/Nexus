"""Tests for nexus.mind.learn — self-improving action memory."""

import sys
import json
import tempfile
import shutil
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# Helpers — each test gets a fresh temp dir and reset module state
# ---------------------------------------------------------------------------

def _reset_learn():
    """Reset learn module state for test isolation."""
    import nexus.mind.learn as learn
    tmpdir = tempfile.mkdtemp()
    orig_dir = learn.LEARN_DIR
    orig_file = learn.LEARN_FILE
    learn.LEARN_DIR = Path(tmpdir)
    learn.LEARN_FILE = Path(tmpdir) / "learned.json"
    learn._store = None
    learn._dirty = False
    learn._pending_failures.clear()
    return tmpdir, orig_dir, orig_file


def _restore_learn(tmpdir, orig_dir, orig_file):
    """Restore learn module state after test."""
    import nexus.mind.learn as learn
    learn.LEARN_DIR = orig_dir
    learn.LEARN_FILE = orig_file
    learn._store = None
    learn._dirty = False
    learn._pending_failures.clear()
    shutil.rmtree(tmpdir, ignore_errors=True)


# ===========================================================================
# Label Lookup
# ===========================================================================

class TestLabelLookup:

    def setup_method(self):
        self._tmpdir, self._orig_dir, self._orig_file = _reset_learn()

    def teardown_method(self):
        _restore_learn(self._tmpdir, self._orig_dir, self._orig_file)

    def test_lookup_empty_store(self):
        from nexus.mind.learn import lookup_label
        assert lookup_label("Save", "TextEdit") is None

    def test_record_and_lookup(self):
        from nexus.mind.learn import record_label, lookup_label
        record_label("Save", "guardar", "TextEdit")
        assert lookup_label("Save", "TextEdit") == "guardar"

    def test_case_insensitive_key(self):
        from nexus.mind.learn import record_label, lookup_label
        record_label("Save", "guardar", "TextEdit")
        assert lookup_label("save", "TextEdit") == "guardar"
        assert lookup_label("SAVE", "TextEdit") == "guardar"

    def test_case_insensitive_app(self):
        from nexus.mind.learn import record_label, lookup_label
        record_label("Save", "guardar", "TextEdit")
        assert lookup_label("Save", "textedit") == "guardar"

    def test_global_fallback(self):
        from nexus.mind.learn import record_label, lookup_label
        record_label("Save", "guardar", "TextEdit")
        # Different app gets the global mapping
        assert lookup_label("Save", "Pages") == "guardar"

    def test_app_specific_takes_precedence(self):
        from nexus.mind.learn import record_label, lookup_label
        record_label("Save", "guardar", "TextEdit")
        record_label("Save", "salvar", "Pages")
        assert lookup_label("Save", "TextEdit") == "guardar"
        assert lookup_label("Save", "Pages") == "salvar"

    def test_identity_not_stored(self):
        from nexus.mind.learn import record_label, lookup_label
        record_label("Save", "Save", "TextEdit")
        assert lookup_label("Save", "TextEdit") is None

    def test_identity_case_insensitive(self):
        from nexus.mind.learn import record_label, lookup_label
        record_label("save", "Save", "TextEdit")
        assert lookup_label("save", "TextEdit") is None

    def test_hit_count_increments(self):
        import nexus.mind.learn as learn
        learn.record_label("Save", "guardar", "TextEdit")
        learn.record_label("Save", "guardar", "TextEdit")
        learn.record_label("Save", "guardar", "TextEdit")
        assert learn._store["labels"]["textedit"]["save"]["hits"] == 3
        assert learn._store["labels"]["_global"]["save"]["hits"] == 3

    def test_lookup_no_app(self):
        from nexus.mind.learn import record_label, lookup_label
        record_label("Save", "guardar", "TextEdit")
        # No app name — falls through to global
        assert lookup_label("Save") == "guardar"

    def test_persists_to_disk(self):
        import nexus.mind.learn as learn
        learn.record_label("Save", "guardar", "TextEdit")
        # Reset in-memory state, force reload from disk
        learn._store = None
        assert learn.lookup_label("Save", "TextEdit") == "guardar"


# ===========================================================================
# Session Correlation
# ===========================================================================

class TestCorrelation:

    def setup_method(self):
        self._tmpdir, self._orig_dir, self._orig_file = _reset_learn()

    def teardown_method(self):
        _restore_learn(self._tmpdir, self._orig_dir, self._orig_file)

    def test_basic_correlation(self):
        from nexus.mind.learn import record_failure, correlate_success, lookup_label
        record_failure("TextEdit", "click", "Save")
        result = correlate_success("TextEdit", "click", "Guardar")
        assert result == "save"
        # Label mapping was created
        assert lookup_label("Save", "TextEdit") == "guardar"

    def test_no_correlation_different_app(self):
        from nexus.mind.learn import record_failure, correlate_success
        record_failure("TextEdit", "click", "Save")
        assert correlate_success("Safari", "click", "Guardar") is None

    def test_no_correlation_different_verb(self):
        from nexus.mind.learn import record_failure, correlate_success
        record_failure("TextEdit", "click", "Save")
        assert correlate_success("TextEdit", "type", "Guardar") is None

    def test_no_correlation_same_target(self):
        from nexus.mind.learn import record_failure, correlate_success
        record_failure("TextEdit", "click", "Save")
        assert correlate_success("TextEdit", "click", "Save") is None

    def test_correlation_expires(self):
        import nexus.mind.learn as learn
        learn.record_failure("TextEdit", "click", "Save")
        # Manually age the failure past the window
        learn._pending_failures[0]["ts"] -= learn.CORRELATION_WINDOW + 1
        assert learn.correlate_success("TextEdit", "click", "Guardar") is None

    def test_failure_consumed_after_correlation(self):
        from nexus.mind.learn import record_failure, correlate_success
        record_failure("TextEdit", "click", "Save")
        correlate_success("TextEdit", "click", "Guardar")
        # Second correlation finds nothing — failure was consumed
        assert correlate_success("TextEdit", "click", "Guardar2") is None

    def test_most_recent_failure_preferred(self):
        from nexus.mind.learn import record_failure, correlate_success
        record_failure("TextEdit", "click", "Save")
        record_failure("TextEdit", "click", "Open")
        result = correlate_success("TextEdit", "click", "Abrir")
        assert result == "open"  # Most recent match

    def test_multiple_failures_independent(self):
        from nexus.mind.learn import record_failure, correlate_success, lookup_label
        record_failure("TextEdit", "click", "Save")
        record_failure("TextEdit", "click", "Open")
        correlate_success("TextEdit", "click", "Abrir")  # consumes Open
        correlate_success("TextEdit", "click", "Guardar")  # consumes Save
        assert lookup_label("Save", "TextEdit") == "guardar"
        assert lookup_label("Open", "TextEdit") == "abrir"

    def test_case_insensitive_correlation(self):
        from nexus.mind.learn import record_failure, correlate_success
        record_failure("TextEdit", "Click", "SAVE")
        result = correlate_success("TextEdit", "click", "guardar")
        assert result == "save"


# ===========================================================================
# Action History
# ===========================================================================

class TestActionHistory:

    def setup_method(self):
        self._tmpdir, self._orig_dir, self._orig_file = _reset_learn()

    def teardown_method(self):
        _restore_learn(self._tmpdir, self._orig_dir, self._orig_file)

    def test_record_success(self):
        import nexus.mind.learn as learn
        learn.record_action("TextEdit", "click Save", True, "click", "Save", "AXPress")
        assert len(learn._store["actions"]) == 1
        assert learn._store["actions"][0]["ok"] is True
        assert learn._store["actions"][0]["method"] == "AXPress"

    def test_record_failure(self):
        import nexus.mind.learn as learn
        learn.record_action("TextEdit", "click Save", False, "click", "Save")
        assert len(learn._store["actions"]) == 1
        assert learn._store["actions"][0]["ok"] is False

    def test_fifo_cap(self):
        import nexus.mind.learn as learn
        for i in range(learn.MAX_ACTIONS + 50):
            learn.record_action("App", f"click {i}", True, "click", str(i))
        assert len(learn._store["actions"]) == learn.MAX_ACTIONS
        # Oldest entries were dropped
        assert learn._store["actions"][0]["target"] == "50"

    def test_method_stats_tracked(self):
        import nexus.mind.learn as learn
        learn.record_action("TextEdit", "click Save", True, "click", "Save", "AXPress")
        learn.record_action("TextEdit", "click Save", True, "click", "Save", "AXPress")
        learn.record_action("TextEdit", "click Open", False, "click", "Open", "coordinate_click")
        assert learn._store["methods"]["textedit"]["AXPress"]["ok"] == 2
        assert learn._store["methods"]["textedit"]["coordinate_click"]["fail"] == 1

    def test_via_label_recorded(self):
        import nexus.mind.learn as learn
        learn.record_action("TextEdit", "click Save", True, "click", "Save",
                            "AXPress", via_label="Save -> guardar")
        assert learn._store["actions"][0]["via_label"] == "Save -> guardar"

    def test_optional_fields_omitted(self):
        import nexus.mind.learn as learn
        learn.record_action("TextEdit", "press cmd+s", True)
        entry = learn._store["actions"][0]
        assert "verb" not in entry
        assert "method" not in entry


# ===========================================================================
# Hints for see()
# ===========================================================================

class TestHints:

    def setup_method(self):
        self._tmpdir, self._orig_dir, self._orig_file = _reset_learn()

    def teardown_method(self):
        _restore_learn(self._tmpdir, self._orig_dir, self._orig_file)

    def test_no_hints_unknown_app(self):
        from nexus.mind.learn import hints_for_app
        assert hints_for_app("UnknownApp") is None

    def test_no_hints_no_app(self):
        from nexus.mind.learn import hints_for_app
        assert hints_for_app(None) is None
        assert hints_for_app("") is None

    def test_label_mappings_shown(self):
        from nexus.mind.learn import record_label, hints_for_app
        record_label("Save", "guardar", "TextEdit")
        record_label("Open", "abrir", "TextEdit")
        hints = hints_for_app("TextEdit")
        assert "save -> guardar" in hints
        assert "open -> abrir" in hints

    def test_label_mappings_sorted_by_hits(self):
        import nexus.mind.learn as learn
        learn.record_label("Save", "guardar", "TextEdit")
        learn.record_label("Save", "guardar", "TextEdit")  # 2 hits
        learn.record_label("Open", "abrir", "TextEdit")     # 1 hit
        hints = learn.hints_for_app("TextEdit")
        # "save" should appear before "open" (more hits)
        assert hints.index("save") < hints.index("open")

    def test_label_mappings_capped_at_5(self):
        import nexus.mind.learn as learn
        for i in range(8):
            learn.record_label(f"label{i}", f"mapped{i}", "App")
        hints = learn.hints_for_app("App")
        assert "... and 3 more" in hints

    def test_method_stats_shown_with_enough_data(self):
        import nexus.mind.learn as learn
        for _ in range(5):
            learn.record_action("TextEdit", "click X", True, "click", "X", "AXPress")
        hints = learn.hints_for_app("TextEdit")
        assert "AXPress" in hints
        assert "100%" in hints

    def test_method_stats_hidden_with_little_data(self):
        import nexus.mind.learn as learn
        learn.record_action("TextEdit", "click X", True, "click", "X", "AXPress")
        hints = learn.hints_for_app("TextEdit")
        # Only 1 data point — methods not shown, but labels might be empty too
        assert hints is None or "AXPress" not in hints


# ===========================================================================
# Stats
# ===========================================================================

class TestStats:

    def setup_method(self):
        self._tmpdir, self._orig_dir, self._orig_file = _reset_learn()

    def teardown_method(self):
        _restore_learn(self._tmpdir, self._orig_dir, self._orig_file)

    def test_empty_stats(self):
        from nexus.mind.learn import stats
        s = stats()
        assert s["label_mappings"] == 0
        assert s["global_mappings"] == 0
        assert s["actions_recorded"] == 0
        assert s["apps_tracked"] == 0

    def test_stats_after_learning(self):
        import nexus.mind.learn as learn
        learn.record_label("Save", "guardar", "TextEdit")
        learn.record_label("Open", "abrir", "TextEdit")
        learn.record_action("TextEdit", "click Save", True)
        learn.record_action("TextEdit", "click Open", True, method="AXPress")
        s = learn.stats()
        assert s["label_mappings"] == 2
        assert s["global_mappings"] == 2
        assert s["actions_recorded"] == 2
        assert s["apps_tracked"] == 1

    def test_stats_multiple_apps(self):
        import nexus.mind.learn as learn
        learn.record_action("TextEdit", "click X", True, method="AXPress")
        learn.record_action("Safari", "click Y", True, method="AXPress")
        s = learn.stats()
        assert s["apps_tracked"] == 2


# ===========================================================================
# Persistence
# ===========================================================================

class TestPersistence:

    def setup_method(self):
        self._tmpdir, self._orig_dir, self._orig_file = _reset_learn()

    def teardown_method(self):
        _restore_learn(self._tmpdir, self._orig_dir, self._orig_file)

    def test_survives_reload(self):
        import nexus.mind.learn as learn
        learn.record_label("Save", "guardar", "TextEdit")
        learn.record_action("TextEdit", "click Save", True, method="AXPress")
        # Force reload
        learn._store = None
        learn._ensure_loaded()
        assert learn.lookup_label("Save", "TextEdit") == "guardar"
        assert len(learn._store["actions"]) == 1

    def test_handles_corrupt_file(self):
        import nexus.mind.learn as learn
        learn.LEARN_FILE.parent.mkdir(parents=True, exist_ok=True)
        learn.LEARN_FILE.write_text("not json {{{")
        learn._store = None
        learn._ensure_loaded()
        # Should get empty store, not crash
        assert learn._store["labels"] == {}

    def test_handles_missing_file(self):
        import nexus.mind.learn as learn
        learn._store = None
        learn._ensure_loaded()
        assert learn._store["labels"] == {}
        assert learn._store["actions"] == []
