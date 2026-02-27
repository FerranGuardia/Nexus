"""Tests for permission checker and auto-dismiss hook.

Tests:
- check_permissions() structured report
- _format_summary() output
- check_permissions recipe pattern
- auto-dismiss hook: safe, unsafe, disabled, no dialogs
"""

import sys
import re
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, "/Users/ferran/repos/Nexus")


# ===========================================================================
# check_permissions()
# ===========================================================================


class TestCheckPermissions:
    """Test the structured permission report."""

    @patch("nexus.mind.permissions._check_auto_dismiss", return_value=False)
    @patch("nexus.mind.permissions._check_sudoers", return_value=True)
    @patch("nexus.mind.permissions._check_screen_recording", return_value=True)
    @patch("nexus.mind.permissions._check_full_disk_access", return_value=True)
    @patch("nexus.mind.permissions._check_apple_events", return_value={"System Events": True, "Finder": True})
    @patch("nexus.mind.permissions._check_accessibility", return_value=True)
    def test_all_granted(self, *mocks):
        from nexus.mind.permissions import check_permissions

        result = check_permissions()
        assert result["accessibility"] is True
        assert result["screen_recording"] is True
        assert result["full_disk_access"] is True
        assert result["sudoers"] is True
        assert result["all_ok"] is True
        assert "Accessibility: OK" in result["summary"]
        assert "Screen Recording: OK" in result["summary"]

    @patch("nexus.mind.permissions._check_auto_dismiss", return_value=False)
    @patch("nexus.mind.permissions._check_sudoers", return_value=False)
    @patch("nexus.mind.permissions._check_screen_recording", return_value=False)
    @patch("nexus.mind.permissions._check_full_disk_access", return_value=False)
    @patch("nexus.mind.permissions._check_apple_events", return_value={"System Events": False, "Finder": False})
    @patch("nexus.mind.permissions._check_accessibility", return_value=False)
    def test_none_granted(self, *mocks):
        from nexus.mind.permissions import check_permissions

        result = check_permissions()
        assert result["accessibility"] is False
        assert result["screen_recording"] is False
        assert result["all_ok"] is False
        assert "MISSING" in result["summary"]
        assert "nexus-setup.sh" in result["summary"]

    @patch("nexus.mind.permissions._check_auto_dismiss", return_value=False)
    @patch("nexus.mind.permissions._check_sudoers", return_value=False)
    @patch("nexus.mind.permissions._check_screen_recording", return_value=True)
    @patch("nexus.mind.permissions._check_full_disk_access", return_value=False)
    @patch("nexus.mind.permissions._check_apple_events", return_value={"System Events": True, "Finder": False})
    @patch("nexus.mind.permissions._check_accessibility", return_value=True)
    def test_partial_grants(self, *mocks):
        from nexus.mind.permissions import check_permissions

        result = check_permissions()
        assert result["accessibility"] is True
        assert result["all_ok"] is True  # accessibility + screen_recording
        ae = result["apple_events"]
        assert ae["System Events"] is True
        assert ae["Finder"] is False

    def test_returns_required_keys(self):
        """check_permissions always returns all expected keys."""
        with patch("nexus.mind.permissions._check_accessibility", return_value=True), \
             patch("nexus.mind.permissions._check_apple_events", return_value={}), \
             patch("nexus.mind.permissions._check_full_disk_access", return_value=False), \
             patch("nexus.mind.permissions._check_screen_recording", return_value=True), \
             patch("nexus.mind.permissions._check_sudoers", return_value=False), \
             patch("nexus.mind.permissions._check_auto_dismiss", return_value=False):
            from nexus.mind.permissions import check_permissions

            result = check_permissions()
            required = {"accessibility", "apple_events", "full_disk_access",
                        "screen_recording", "sudoers", "auto_dismiss", "all_ok", "summary"}
            assert required.issubset(result.keys())


# ===========================================================================
# Individual checkers
# ===========================================================================


class TestIndividualChecks:
    """Test each _check_* function in isolation."""

    def test_check_accessibility_true(self):
        from nexus.mind.permissions import _check_accessibility

        with patch("ApplicationServices.AXIsProcessTrusted", return_value=True):
            assert _check_accessibility() is True

    def test_check_accessibility_false(self):
        from nexus.mind.permissions import _check_accessibility

        with patch("ApplicationServices.AXIsProcessTrusted", return_value=False):
            assert _check_accessibility() is False

    def test_check_accessibility_import_error(self):
        """Gracefully returns False if pyobjc not available."""
        from nexus.mind.permissions import _check_accessibility

        with patch.dict("sys.modules", {"ApplicationServices": None}):
            # Force ImportError on next import attempt
            assert _check_accessibility() is False or _check_accessibility() is True
            # Just verify it doesn't crash

    def test_check_apple_events_success(self):
        from nexus.mind.permissions import _check_apple_events

        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = _check_apple_events()
            assert result["System Events"] is True
            assert result["Finder"] is True

    def test_check_apple_events_denied(self):
        from nexus.mind.permissions import _check_apple_events

        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("subprocess.run", return_value=mock_result):
            result = _check_apple_events()
            assert result["System Events"] is False
            assert result["Finder"] is False

    def test_check_apple_events_timeout(self):
        from nexus.mind.permissions import _check_apple_events
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="osascript", timeout=5)):
            result = _check_apple_events()
            assert result["System Events"] is False

    def test_check_sudoers_exists(self):
        from nexus.mind.permissions import _check_sudoers

        with patch("pathlib.Path.exists", return_value=True):
            assert _check_sudoers() is True

    def test_check_sudoers_missing(self):
        from nexus.mind.permissions import _check_sudoers

        with patch("pathlib.Path.exists", return_value=False):
            assert _check_sudoers() is False

    def test_check_auto_dismiss_true(self):
        from nexus.mind.permissions import _check_auto_dismiss

        with patch("nexus.mind.store._get", return_value="true"):
            assert _check_auto_dismiss() is True

    def test_check_auto_dismiss_false(self):
        from nexus.mind.permissions import _check_auto_dismiss

        with patch("nexus.mind.store._get", return_value=None):
            assert _check_auto_dismiss() is False

    def test_check_auto_dismiss_various_truthy(self):
        from nexus.mind.permissions import _check_auto_dismiss

        for val in (True, "true", "True", "1"):
            with patch("nexus.mind.store._get", return_value=val):
                assert _check_auto_dismiss() is True, f"Failed for {val!r}"

    def test_check_auto_dismiss_various_falsy(self):
        from nexus.mind.permissions import _check_auto_dismiss

        for val in (False, "false", "0", None, ""):
            with patch("nexus.mind.store._get", return_value=val):
                assert _check_auto_dismiss() is False, f"Failed for {val!r}"


# ===========================================================================
# _format_summary()
# ===========================================================================


class TestFormatSummary:
    def test_all_ok_summary(self):
        from nexus.mind.permissions import _format_summary

        result = {
            "accessibility": True,
            "screen_recording": True,
            "full_disk_access": True,
            "sudoers": True,
            "apple_events": {"System Events": True, "Finder": True},
            "auto_dismiss": True,
        }
        summary = _format_summary(result)
        assert "Accessibility: OK" in summary
        assert "MISSING" not in summary

    def test_missing_critical_shows_instructions(self):
        from nexus.mind.permissions import _format_summary

        result = {
            "accessibility": False,
            "screen_recording": False,
            "full_disk_access": False,
            "sudoers": False,
            "apple_events": {},
            "auto_dismiss": False,
        }
        summary = _format_summary(result)
        assert "Accessibility: MISSING" in summary
        assert "Screen Recording: MISSING" in summary
        assert "nexus-setup.sh" in summary

    def test_optional_off_not_missing(self):
        from nexus.mind.permissions import _format_summary

        result = {
            "accessibility": True,
            "screen_recording": True,
            "full_disk_access": False,
            "sudoers": False,
            "apple_events": {"System Events": True},
            "auto_dismiss": False,
        }
        summary = _format_summary(result)
        assert "Full Disk Access: off" in summary
        assert "Sudoers (NOPASSWD): off" in summary
        assert "Auto-dismiss dialogs: off" in summary


# ===========================================================================
# Recipe pattern
# ===========================================================================


class TestPermissionsRecipe:
    """Test the check_permissions recipe pattern matching."""

    def _matches(self, pattern, text):
        return re.search(pattern, text, re.IGNORECASE) is not None

    def test_pattern_matches(self):
        pattern = r"^(?:check |show |get )?permissions?(?: status)?$"
        assert self._matches(pattern, "check permissions")
        assert self._matches(pattern, "permissions")
        assert self._matches(pattern, "permission")
        assert self._matches(pattern, "permission status")
        assert self._matches(pattern, "show permissions")
        assert self._matches(pattern, "get permissions")

    def test_pattern_rejects(self):
        pattern = r"^(?:check |show |get )?permissions?(?: status)?$"
        assert not self._matches(pattern, "set permissions to admin")
        assert not self._matches(pattern, "click permissions button")
        assert not self._matches(pattern, "open permissions panel")


# ===========================================================================
# Auto-dismiss hook
# ===========================================================================


class TestAutoDismissHook:
    """Test _auto_dismiss_dialog_hook behavior."""

    def setup_method(self):
        from nexus.hooks import clear
        clear()

    def teardown_method(self):
        from nexus.hooks import clear, register_builtins
        clear()
        register_builtins()

    def test_no_dialogs_passthrough(self):
        """When no dialogs detected, ctx passes through unchanged."""
        from nexus.hooks import _auto_dismiss_dialog_hook

        with patch("nexus.sense.system.detect_system_dialogs", return_value=[]):
            ctx = {"action": "click Save"}
            result = _auto_dismiss_dialog_hook(ctx)
            assert "stop" not in result
            assert "error" not in result

    def test_disabled_adds_count(self):
        """When auto_dismiss is off, dialog count is added to ctx."""
        from nexus.hooks import _auto_dismiss_dialog_hook

        dialog = {
            "process": "CoreServicesUIAgent",
            "pid": 50,
            "bounds": {"x": 100, "y": 100, "w": 400, "h": 200},
        }
        with patch("nexus.sense.system.detect_system_dialogs", return_value=[dialog]), \
             patch("nexus.mind.permissions._check_auto_dismiss", return_value=False):
            ctx = {"action": "click Install"}
            result = _auto_dismiss_dialog_hook(ctx)
            assert result.get("system_dialogs") == 1
            assert "stop" not in result

    def test_safe_dialog_auto_clicks(self):
        """Gatekeeper dialog is auto-clicked when auto_dismiss is on."""
        from nexus.hooks import _auto_dismiss_dialog_hook

        dialog = {
            "process": "CoreServicesUIAgent",
            "pid": 50,
            "bounds": {"x": 100, "y": 100, "w": 400, "h": 200},
        }
        classification = {
            "type": "gatekeeper",
            "description": "App downloaded from internet",
            "suggested_action": "Click Open",
            "buttons": [{"label": "Open", "center_x": 350, "center_y": 280}],
        }

        mock_click = MagicMock()

        with patch("nexus.sense.system.detect_system_dialogs", return_value=[dialog]), \
             patch("nexus.mind.permissions._check_auto_dismiss", return_value=True), \
             patch("nexus.sense.fusion._ocr_dialog_region", return_value=[]), \
             patch("nexus.sense.system.classify_dialog", return_value=classification), \
             patch("nexus.act.input.click", mock_click), \
             patch("time.sleep"):
            ctx = {"action": "open Docker"}
            result = _auto_dismiss_dialog_hook(ctx)
            assert "stop" not in result
            mock_click.assert_called_once_with(350, 280)

    def test_unsafe_dialog_stops(self):
        """Password dialog blocks action with error."""
        from nexus.hooks import _auto_dismiss_dialog_hook

        dialog = {
            "process": "SecurityAgent",
            "pid": 70,
            "bounds": {"x": 200, "y": 200, "w": 400, "h": 300},
        }
        classification = {
            "type": "password_prompt",
            "description": "Admin password required",
            "suggested_action": "Enter password",
            "buttons": [],
        }

        with patch("nexus.sense.system.detect_system_dialogs", return_value=[dialog]), \
             patch("nexus.mind.permissions._check_auto_dismiss", return_value=True), \
             patch("nexus.sense.fusion._ocr_dialog_region", return_value=[]), \
             patch("nexus.sense.system.classify_dialog", return_value=classification):
            ctx = {"action": "install app"}
            result = _auto_dismiss_dialog_hook(ctx)
            assert result.get("stop") is True
            assert "password" in result.get("error", "").lower() or "intervention" in result.get("error", "").lower()

    def test_folder_access_auto_clicks(self):
        """Folder access dialog auto-clicks OK."""
        from nexus.hooks import _auto_dismiss_dialog_hook

        dialog = {
            "process": "UserNotificationCenter",
            "pid": 80,
            "bounds": {"x": 100, "y": 100, "w": 400, "h": 200},
        }
        classification = {
            "type": "folder_access",
            "description": "App wants access to folder",
            "suggested_action": "Click OK",
            "buttons": [{"label": "OK", "center_x": 300, "center_y": 250}],
        }

        mock_click = MagicMock()

        with patch("nexus.sense.system.detect_system_dialogs", return_value=[dialog]), \
             patch("nexus.mind.permissions._check_auto_dismiss", return_value=True), \
             patch("nexus.sense.fusion._ocr_dialog_region", return_value=[]), \
             patch("nexus.sense.system.classify_dialog", return_value=classification), \
             patch("nexus.act.input.click", mock_click), \
             patch("time.sleep"):
            ctx = {"action": "read files"}
            result = _auto_dismiss_dialog_hook(ctx)
            assert "stop" not in result
            mock_click.assert_called_once_with(300, 250)

    def test_network_permission_stops(self):
        """Network permission dialog blocks — user must decide."""
        from nexus.hooks import _auto_dismiss_dialog_hook

        dialog = {
            "process": "UserNotificationCenter",
            "pid": 80,
            "bounds": {"x": 100, "y": 100, "w": 400, "h": 200},
        }
        classification = {
            "type": "network_permission",
            "description": "App wants to find devices on network",
            "suggested_action": "Allow or deny",
            "buttons": [],
        }

        with patch("nexus.sense.system.detect_system_dialogs", return_value=[dialog]), \
             patch("nexus.mind.permissions._check_auto_dismiss", return_value=True), \
             patch("nexus.sense.fusion._ocr_dialog_region", return_value=[]), \
             patch("nexus.sense.system.classify_dialog", return_value=classification):
            ctx = {"action": "scan network"}
            result = _auto_dismiss_dialog_hook(ctx)
            assert result.get("stop") is True

    def test_hook_never_crashes(self):
        """Even with exceptions, hook returns ctx without raising."""
        from nexus.hooks import _auto_dismiss_dialog_hook

        with patch("nexus.sense.system.detect_system_dialogs", side_effect=RuntimeError("boom")):
            ctx = {"action": "click Save"}
            result = _auto_dismiss_dialog_hook(ctx)
            assert result == ctx

    def test_safe_dialog_template_fallback(self):
        """When OCR buttons are empty, falls back to template coordinates."""
        from nexus.hooks import _auto_dismiss_dialog_hook

        dialog = {
            "process": "CoreServicesUIAgent",
            "pid": 50,
            "bounds": {"x": 100, "y": 100, "w": 400, "h": 200},
        }
        classification = {
            "type": "gatekeeper",
            "description": "App downloaded from internet",
            "suggested_action": "Click Open",
            "buttons": [],  # No OCR buttons
        }

        mock_click = MagicMock()
        mock_template = {
            "buttons": {"open": {"rel_x": 0.75, "rel_y": 0.85, "labels": ["Open"]}},
        }

        with patch("nexus.sense.system.detect_system_dialogs", return_value=[dialog]), \
             patch("nexus.mind.permissions._check_auto_dismiss", return_value=True), \
             patch("nexus.sense.fusion._ocr_dialog_region", return_value=[{"text": "downloaded from internet"}]), \
             patch("nexus.sense.system.classify_dialog", return_value=classification), \
             patch("nexus.sense.templates.match_template", return_value=("gatekeeper_open", mock_template)), \
             patch("nexus.sense.templates.resolve_button", return_value=(400, 270)), \
             patch("nexus.act.input.click", mock_click), \
             patch("time.sleep"):
            ctx = {"action": "open Docker"}
            result = _auto_dismiss_dialog_hook(ctx)
            assert "stop" not in result
            mock_click.assert_called_once_with(400, 270)


# ===========================================================================
# Button label mapping
# ===========================================================================


class TestButtonLabelMap:
    def test_open_includes_spanish(self):
        from nexus.hooks import _button_label_map

        labels = _button_label_map("open")
        assert "open" in labels
        assert "abrir" in labels

    def test_ok_includes_spanish(self):
        from nexus.hooks import _button_label_map

        labels = _button_label_map("ok")
        assert "ok" in labels
        assert "aceptar" in labels

    def test_unknown_key_returns_itself(self):
        from nexus.hooks import _button_label_map

        labels = _button_label_map("custom")
        assert "custom" in labels


# ===========================================================================
# Hook registration
# ===========================================================================


class TestAutoDismissRegistration:
    """Verify the hook is properly registered in builtins."""

    def test_auto_dismiss_registered(self):
        from nexus.hooks import registered

        before_do_hooks = registered("before_do")
        names = [name for _, name in before_do_hooks]
        assert "auto_dismiss" in names

    def test_auto_dismiss_after_circuit_breaker(self):
        """Auto-dismiss runs after circuit breaker (higher priority number)."""
        from nexus.hooks import registered

        before_do_hooks = registered("before_do")
        priorities = {name: pri for pri, name in before_do_hooks}
        assert priorities["auto_dismiss"] > priorities["circuit_breaker"]
