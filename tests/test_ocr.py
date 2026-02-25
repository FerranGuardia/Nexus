"""Tests for OCR module (nexus/sense/ocr.py).

OCR relies on Apple Vision framework which is macOS-only.
These tests mock the Vision framework calls to be runnable anywhere.
"""

from unittest.mock import patch, MagicMock
import pytest

from nexus.sense import ocr


class TestOcrToElements:
    def test_converts_basic_result(self):
        results = [
            {
                "text": "Save",
                "confidence": 0.98,
                "bounds": {"x": 100, "y": 200, "w": 60, "h": 20},
                "center": {"x": 130, "y": 210},
                "source": "ocr",
            },
        ]
        elements = ocr.ocr_to_elements(results)
        assert len(elements) == 1
        assert elements[0]["role"] == "text (OCR)"
        assert elements[0]["label"] == "Save"
        assert elements[0]["pos"] == (130, 210)
        assert elements[0]["source"] == "ocr"
        assert elements[0]["confidence"] == 0.98

    def test_empty_results(self):
        assert ocr.ocr_to_elements([]) == []

    def test_multiple_results(self):
        results = [
            {"text": "Open", "confidence": 0.95, "bounds": {"x": 0, "y": 0, "w": 50, "h": 15},
             "center": {"x": 25, "y": 7}, "source": "ocr"},
            {"text": "Cancel", "confidence": 0.93, "bounds": {"x": 100, "y": 0, "w": 60, "h": 15},
             "center": {"x": 130, "y": 7}, "source": "ocr"},
        ]
        elements = ocr.ocr_to_elements(results)
        assert len(elements) == 2
        assert elements[0]["label"] == "Open"
        assert elements[1]["label"] == "Cancel"


class TestFindTextInOcr:
    def _results(self):
        return [
            {"text": "Open", "confidence": 0.95, "center": {"x": 100, "y": 50}},
            {"text": "Cancel", "confidence": 0.93, "center": {"x": 200, "y": 50}},
            {"text": "Some long description text", "confidence": 0.88, "center": {"x": 150, "y": 100}},
            {"text": "Low confidence", "confidence": 0.3, "center": {"x": 150, "y": 150}},
        ]

    def test_exact_match(self):
        result = ocr.find_text_in_ocr(self._results(), "Open")
        assert result is not None
        assert result["text"] == "Open"

    def test_case_insensitive(self):
        result = ocr.find_text_in_ocr(self._results(), "open")
        assert result is not None
        assert result["text"] == "Open"

    def test_partial_match(self):
        result = ocr.find_text_in_ocr(self._results(), "Cancel")
        assert result is not None
        assert result["text"] == "Cancel"

    def test_no_match(self):
        result = ocr.find_text_in_ocr(self._results(), "Delete")
        assert result is None

    def test_below_threshold(self):
        result = ocr.find_text_in_ocr(self._results(), "Low confidence", threshold=0.5)
        assert result is None

    def test_empty_results(self):
        result = ocr.find_text_in_ocr([], "Open")
        assert result is None

    def test_prefers_exact_over_partial(self):
        results = [
            {"text": "Open Anyway", "confidence": 0.95, "center": {"x": 100, "y": 50}},
            {"text": "Open", "confidence": 0.90, "center": {"x": 200, "y": 50}},
        ]
        result = ocr.find_text_in_ocr(results, "Open")
        assert result["text"] == "Open"

    def test_prefers_shortest_partial(self):
        results = [
            {"text": "Open this very long button label", "confidence": 0.95, "center": {"x": 100, "y": 50}},
            {"text": "Open Now", "confidence": 0.95, "center": {"x": 200, "y": 50}},
        ]
        result = ocr.find_text_in_ocr(results, "Open")
        assert result["text"] == "Open Now"


class TestOcrRegion:
    @patch("nexus.sense.ocr._import_vision")
    def test_returns_empty_when_vision_unavailable(self, mock_import):
        mock_import.return_value = (None, None, None)
        result = ocr.ocr_region(0, 0, 400, 300)
        assert result == []

    @patch("nexus.sense.ocr._import_vision")
    @patch("nexus.sense.ocr.CGWindowListCreateImage", return_value=None)
    def test_returns_empty_when_capture_fails(self, mock_cg, mock_import):
        mock_import.return_value = (MagicMock(), MagicMock(), MagicMock())
        result = ocr.ocr_region(0, 0, 400, 300)
        assert result == []


class TestOcrImageFile:
    @patch("nexus.sense.ocr._import_vision")
    def test_returns_empty_when_vision_unavailable(self, mock_import):
        mock_import.return_value = (None, None, None)
        result = ocr.ocr_image_file("/tmp/nonexistent.png")
        assert result == []
