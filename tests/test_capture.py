"""Tests for capture module (nexus/sense/capture.py)."""

from unittest.mock import patch, MagicMock
import pytest

from nexus.sense import capture


class TestMacosVersion:
    @patch("platform.mac_ver", return_value=("15.3.1", ("", "", ""), ""))
    def test_parses_version(self, mock_ver):
        assert capture._macos_version() == 15

    @patch("platform.mac_ver", return_value=("14.0", ("", "", ""), ""))
    def test_parses_14(self, mock_ver):
        assert capture._macos_version() == 14

    @patch("platform.mac_ver", return_value=("", ("", "", ""), ""))
    def test_handles_empty(self, mock_ver):
        assert capture._macos_version() == 0


class TestHasScreenCaptureKit:
    @patch("nexus.sense.capture._macos_version", return_value=15)
    def test_available_on_15(self, mock_ver):
        assert capture._has_screencapturekit() is True

    @patch("nexus.sense.capture._macos_version", return_value=14)
    def test_available_on_14(self, mock_ver):
        assert capture._has_screencapturekit() is True

    @patch("nexus.sense.capture._macos_version", return_value=13)
    def test_not_available_on_13(self, mock_ver):
        assert capture._has_screencapturekit() is False


class TestCaptureDialog:
    @patch("nexus.sense.capture.capture_window", return_value=MagicMock())
    def test_uses_window_id_if_available(self, mock_win):
        dialog = {"window_id": 12345, "bounds": {"x": 0, "y": 0, "w": 400, "h": 300}}
        result = capture.capture_dialog(dialog)
        mock_win.assert_called_once_with(12345)
        assert result is not None

    @patch("nexus.sense.capture.capture_window", return_value=None)
    @patch("nexus.sense.capture.capture_region", return_value=MagicMock())
    def test_falls_back_to_region(self, mock_region, mock_win):
        dialog = {"window_id": 12345, "bounds": {"x": 100, "y": 200, "w": 400, "h": 300}}
        result = capture.capture_dialog(dialog)
        mock_region.assert_called_once_with(100, 200, 400, 300)

    def test_no_bounds_returns_none(self):
        dialog = {"window_id": 0, "bounds": {"x": 0, "y": 0, "w": 0, "h": 0}}
        with patch("nexus.sense.capture.capture_window", return_value=None):
            result = capture.capture_dialog(dialog)
            assert result is None


class TestImageToBase64:
    def test_none_image(self):
        assert capture.image_to_base64(None) is None

    def test_converts_small_image(self):
        from PIL import Image
        img = Image.new("RGB", (100, 100), color="red")
        result = capture.image_to_base64(img)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_downscales_large_image(self):
        from PIL import Image
        img = Image.new("RGB", (3000, 2000), color="blue")
        result = capture.image_to_base64(img, max_width=1280)
        assert isinstance(result, str)

    def test_handles_rgba(self):
        from PIL import Image
        img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        result = capture.image_to_base64(img)
        assert isinstance(result, str)


class TestImageToFile:
    def test_none_image(self):
        assert capture.image_to_file(None, "/tmp/test.jpg") is None

    def test_saves_image(self, tmp_path):
        from PIL import Image
        img = Image.new("RGB", (100, 100), color="green")
        path = str(tmp_path / "test.jpg")
        result = capture.image_to_file(img, path)
        assert result == path
        import os
        assert os.path.exists(path)
