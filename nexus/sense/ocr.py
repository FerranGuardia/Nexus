"""OCR via Apple Vision Framework — on-device text recognition.

Falls back to this when the accessibility tree returns too few elements.
Zero new dependencies — uses pyobjc (already installed) to call VNRecognizeTextRequest.

Returns text elements with bounding boxes that can be clicked via coordinates.
"""

import io
import os
import tempfile

from Quartz import (
    CGWindowListCreateImage,
    CGRectMake,
    kCGWindowListOptionOnScreenOnly,
    kCGNullWindowID,
    kCGWindowImageDefault,
    CGImageGetWidth,
    CGImageGetHeight,
)


def _import_vision():
    """Lazy import Vision framework — fails gracefully if not available."""
    try:
        import Vision
        from Foundation import NSURL
        from Quartz import CIImage
        return Vision, NSURL, CIImage
    except ImportError:
        return None, None, None


def ocr_region(x, y, w, h, languages=None):
    """OCR a screen region. Returns list of {text, confidence, bounds}.

    Args:
        x, y, w, h: Screen region in points.
        languages: List of language codes (default: ["en", "es"]).

    Returns:
        List of dicts: [{text, confidence, bounds: {x, y, w, h}}]
        bounds are in screen coordinates (ready for pyautogui.click).
    """
    Vision, NSURL, CIImage = _import_vision()
    if Vision is None:
        return []

    # Capture the region
    rect = CGRectMake(x, y, w, h)
    cg_image = CGWindowListCreateImage(
        rect,
        kCGWindowListOptionOnScreenOnly,
        kCGNullWindowID,
        kCGWindowImageDefault,
    )
    if not cg_image:
        return []

    img_w = CGImageGetWidth(cg_image)
    img_h = CGImageGetHeight(cg_image)
    if img_w == 0 or img_h == 0:
        return []

    return _ocr_cgimage(cg_image, img_w, img_h, x, y, languages)


def ocr_image_file(path, offset_x=0, offset_y=0, languages=None):
    """OCR an image file. Returns list of {text, confidence, bounds}.

    Args:
        path: Path to image file (PNG, JPEG, etc.)
        offset_x, offset_y: Offset to add to bounds (for screen coordinates).
        languages: List of language codes.
    """
    Vision, NSURL, CIImage = _import_vision()
    if Vision is None:
        return []

    input_url = NSURL.fileURLWithPath_(path)
    ci_image = CIImage.imageWithContentsOfURL_(input_url)
    if ci_image is None:
        return []

    extent = ci_image.extent()
    img_w = int(extent.size.width)
    img_h = int(extent.size.height)

    return _ocr_ciimage(ci_image, img_w, img_h, offset_x, offset_y, languages)


def _ocr_cgimage(cg_image, img_w, img_h, offset_x, offset_y, languages):
    """Run OCR on a CGImage."""
    Vision, NSURL, CIImage = _import_vision()
    if Vision is None:
        return []

    # Convert CGImage to CIImage for Vision
    ci_image = CIImage.imageWithCGImage_(cg_image)
    return _ocr_ciimage(ci_image, img_w, img_h, offset_x, offset_y, languages)


def _ocr_ciimage(ci_image, img_w, img_h, offset_x, offset_y, languages):
    """Run OCR on a CIImage. Core implementation."""
    Vision, NSURL, CIImage = _import_vision()
    if Vision is None:
        return []

    if languages is None:
        languages = ["en", "es"]

    results = []

    def handler(request, error):
        if error:
            return
        observations = request.results()
        if not observations:
            return

        for obs in observations:
            candidates = obs.topCandidates_(1)
            if not candidates:
                continue
            candidate = candidates[0]
            text = candidate.string()
            confidence = candidate.confidence()

            # Get bounding box (normalized 0-1, origin bottom-left)
            bbox = obs.boundingBox()
            # Convert from Vision coordinates (bottom-left origin, normalized)
            # to screen coordinates (top-left origin, pixels)
            bx = bbox.origin.x * img_w + offset_x
            by = (1.0 - bbox.origin.y - bbox.size.height) * img_h + offset_y
            bw = bbox.size.width * img_w
            bh = bbox.size.height * img_h

            results.append({
                "text": text,
                "confidence": round(confidence, 3),
                "bounds": {
                    "x": round(bx),
                    "y": round(by),
                    "w": round(bw),
                    "h": round(bh),
                },
                "center": {
                    "x": round(bx + bw / 2),
                    "y": round(by + bh / 2),
                },
                "source": "ocr",
            })

    # Create and configure the request
    request = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(handler)
    request.setRecognitionLevel_(1)  # 1 = accurate, 0 = fast
    request.setRecognitionLanguages_(languages)
    request.setUsesLanguageCorrection_(True)

    # Run
    request_handler = Vision.VNImageRequestHandler.alloc().initWithCIImage_options_(
        ci_image, None
    )
    success, err = request_handler.performRequests_error_([request], None)

    return results


def ocr_to_elements(ocr_results):
    """Convert OCR results to element dicts compatible with see() output.

    Returns elements that look like AX elements but with source="ocr"
    and click coordinates based on text bounding boxes.
    """
    elements = []
    for r in ocr_results:
        elements.append({
            "role": "text (OCR)",
            "label": r["text"],
            "value": "",
            "pos": (r["center"]["x"], r["center"]["y"]),
            "enabled": True,
            "focused": False,
            "source": "ocr",
            "confidence": r["confidence"],
            "_bounds": r["bounds"],
        })
    return elements


def find_text_in_ocr(ocr_results, target, threshold=0.5):
    """Find a specific text in OCR results. Returns best match or None.

    Args:
        ocr_results: List from ocr_region() or ocr_image_file().
        target: Text to find (case-insensitive partial match).
        threshold: Minimum confidence (0-1).

    Returns:
        Best matching result dict, or None.
    """
    target_lower = target.lower()
    matches = []
    for r in ocr_results:
        if r["confidence"] < threshold:
            continue
        text_lower = r["text"].lower()
        if target_lower in text_lower or text_lower in target_lower:
            matches.append(r)

    if not matches:
        return None

    # Prefer exact matches, then shortest (most precise)
    exact = [m for m in matches if m["text"].lower() == target_lower]
    if exact:
        return max(exact, key=lambda m: m["confidence"])
    return min(matches, key=lambda m: len(m["text"]))
