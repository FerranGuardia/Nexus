"""Tests for system dialog detection (nexus/sense/system.py)."""

from unittest.mock import patch, MagicMock
import pytest

from nexus.sense import system


# ── detect_system_dialogs ──


class TestDetectSystemDialogs:
    def _make_window(self, owner, pid=100, title="", x=0, y=0, w=400, h=300, layer=0, on_screen=True):
        return {
            "kCGWindowOwnerName": owner,
            "kCGWindowOwnerPID": pid,
            "kCGWindowName": title,
            "kCGWindowBounds": {"X": x, "Y": y, "Width": w, "Height": h},
            "kCGWindowLayer": layer,
            "kCGWindowIsOnscreen": on_screen,
            "kCGWindowNumber": 12345,
        }

    @patch("nexus.sense.system.CGWindowListCopyWindowInfo")
    def test_finds_gatekeeper_dialog(self, mock_cg):
        mock_cg.return_value = [
            self._make_window("CoreServicesUIAgent", pid=50, w=450, h=200),
            self._make_window("Finder", pid=60),
        ]
        result = system.detect_system_dialogs()
        assert len(result) == 1
        assert result[0]["process"] == "CoreServicesUIAgent"
        assert result[0]["pid"] == 50
        assert result[0]["bounds"]["w"] == 450

    @patch("nexus.sense.system.CGWindowListCopyWindowInfo")
    def test_finds_security_agent(self, mock_cg):
        mock_cg.return_value = [
            self._make_window("SecurityAgent", pid=70, w=400, h=300),
        ]
        result = system.detect_system_dialogs()
        assert len(result) == 1
        assert result[0]["process"] == "SecurityAgent"

    @patch("nexus.sense.system.CGWindowListCopyWindowInfo")
    def test_finds_user_notification_center(self, mock_cg):
        mock_cg.return_value = [
            self._make_window("UserNotificationCenter", pid=80),
        ]
        result = system.detect_system_dialogs()
        assert len(result) == 1

    @patch("nexus.sense.system.CGWindowListCopyWindowInfo")
    def test_ignores_normal_apps(self, mock_cg):
        mock_cg.return_value = [
            self._make_window("Safari", pid=60),
            self._make_window("Finder", pid=61),
            self._make_window("Terminal", pid=62),
        ]
        result = system.detect_system_dialogs()
        assert len(result) == 0

    @patch("nexus.sense.system.CGWindowListCopyWindowInfo")
    def test_ignores_tiny_windows(self, mock_cg):
        mock_cg.return_value = [
            self._make_window("CoreServicesUIAgent", w=10, h=10),
        ]
        result = system.detect_system_dialogs()
        assert len(result) == 0

    @patch("nexus.sense.system.CGWindowListCopyWindowInfo")
    def test_multiple_dialogs(self, mock_cg):
        mock_cg.return_value = [
            self._make_window("CoreServicesUIAgent", pid=50),
            self._make_window("SecurityAgent", pid=70),
        ]
        result = system.detect_system_dialogs()
        assert len(result) == 2

    @patch("nexus.sense.system.CGWindowListCopyWindowInfo")
    def test_no_windows(self, mock_cg):
        mock_cg.return_value = []
        result = system.detect_system_dialogs()
        assert result == []

    @patch("nexus.sense.system.CGWindowListCopyWindowInfo")
    def test_none_windows(self, mock_cg):
        mock_cg.return_value = None
        result = system.detect_system_dialogs()
        assert result == []

    @patch("nexus.sense.system.CGWindowListCopyWindowInfo", side_effect=Exception("fail"))
    def test_exception_returns_empty(self, mock_cg):
        result = system.detect_system_dialogs()
        assert result == []

    @patch("nexus.sense.system.CGWindowListCopyWindowInfo")
    def test_window_id_included(self, mock_cg):
        mock_cg.return_value = [
            self._make_window("CoreServicesUIAgent", pid=50),
        ]
        result = system.detect_system_dialogs()
        assert result[0]["window_id"] == 12345


# ── classify_dialog ──


class TestClassifyDialog:
    def _dialog(self, process="CoreServicesUIAgent"):
        return {"process": process, "pid": 50, "bounds": {"x": 0, "y": 0, "w": 400, "h": 300}}

    def _ocr(self, texts):
        """Create fake OCR results from text strings."""
        return [{"text": t, "confidence": 0.95, "center": {"x": 100, "y": 100}} for t in texts]

    def test_gatekeeper_dialog(self):
        result = system.classify_dialog(
            self._dialog(),
            self._ocr(["Docker is an app downloaded from the internet", "Open", "Cancel"]),
        )
        assert result["type"] == "gatekeeper"
        assert "Gatekeeper" in result["description"]

    def test_gatekeeper_spanish(self):
        result = system.classify_dialog(
            self._dialog(),
            self._ocr(["aplicación descargada de internet", "Abrir", "Cancelar"]),
        )
        assert result["type"] == "gatekeeper"

    def test_gatekeeper_verifying(self):
        result = system.classify_dialog(
            self._dialog(),
            self._ocr(["Verifying Docker Desktop", "checking its security"]),
        )
        assert result["type"] == "gatekeeper_verifying"

    def test_password_prompt(self):
        result = system.classify_dialog(
            self._dialog("SecurityAgent"),
            self._ocr(["Enter your password to allow changes", "OK", "Cancel"]),
        )
        assert result["type"] == "password_prompt"

    def test_network_permission(self):
        result = system.classify_dialog(
            self._dialog("UserNotificationCenter"),
            self._ocr(["Docker wants to find devices on your local network", "Allow", "Don't Allow"]),
        )
        assert result["type"] == "network_permission"

    def test_folder_access(self):
        result = system.classify_dialog(
            self._dialog("UserNotificationCenter"),
            self._ocr(["App would like to access files in your Documents", "OK", "Don't Allow"]),
        )
        assert result["type"] == "folder_permission"

    def test_no_ocr_data(self):
        result = system.classify_dialog(self._dialog(), None)
        assert result["type"] == "system_prompt"

    def test_empty_ocr(self):
        result = system.classify_dialog(self._dialog(), [])
        assert result["type"] == "system_prompt"

    def test_buttons_extracted(self):
        result = system.classify_dialog(
            self._dialog(),
            self._ocr(["downloaded from the internet", "Open", "Cancel"]),
        )
        button_labels = [b["label"] for b in result["buttons"]]
        assert "Open" in button_labels


# ── format_system_dialogs ──


class TestFormatSystemDialogs:
    def test_empty_list(self):
        assert system.format_system_dialogs([]) == ""

    def test_single_dialog_no_classification(self):
        dialogs = [{
            "process": "CoreServicesUIAgent",
            "pid": 50,
            "title": "",
            "bounds": {"x": 100, "y": 200, "w": 400, "h": 300},
        }]
        result = system.format_system_dialogs(dialogs)
        assert "SYSTEM DIALOGS" in result
        assert "CoreServicesUIAgent" in result

    def test_with_classification(self):
        dialogs = [{
            "process": "CoreServicesUIAgent",
            "pid": 50,
            "title": "",
            "bounds": {"x": 100, "y": 200, "w": 400, "h": 300},
        }]
        classifications = [{
            "type": "gatekeeper",
            "description": "Gatekeeper: app from internet",
            "suggested_action": "Click Open",
            "buttons": [{"label": "Open", "center_x": 300, "center_y": 450}],
        }]
        result = system.format_system_dialogs(dialogs, classifications)
        assert "GATEKEEPER" in result
        assert "Click Open" in result
        assert '"Open"' in result


# ── _find_buttons ──


class TestFindButtons:
    def test_finds_matching_buttons(self):
        ocr = [
            {"text": "Open", "center": {"x": 300, "y": 250}},
            {"text": "Cancel", "center": {"x": 200, "y": 250}},
            {"text": "Some other text", "center": {"x": 200, "y": 100}},
        ]
        result = system._find_buttons(ocr, ["open", "cancel"])
        assert len(result) == 2

    def test_case_insensitive(self):
        ocr = [{"text": "OPEN", "center": {"x": 300, "y": 250}}]
        result = system._find_buttons(ocr, ["open"])
        assert len(result) == 1

    def test_no_match(self):
        ocr = [{"text": "Something", "center": {"x": 300, "y": 250}}]
        result = system._find_buttons(ocr, ["open", "cancel"])
        assert len(result) == 0

    def test_empty_ocr(self):
        result = system._find_buttons([], ["open"])
        assert result == []

    def test_none_ocr(self):
        result = system._find_buttons(None, ["open"])
        assert result == []
