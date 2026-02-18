"""Oculus OCR — text recognition from screen regions via Windows OCR (WinRT).

Pure functions: take params, return dict. No side effects beyond screenshots.
"""

import asyncio
import os
import time

import pyautogui
from PIL import Image

SCREENSHOT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".tmp-screenshots",
)


async def _ocr_image_async(image: Image.Image, lang: str = "en"):
    """Run Windows OCR on a PIL Image. Returns list of word dicts."""
    import io
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.globalization import Language
    from winrt.windows.graphics.imaging import BitmapDecoder, SoftwareBitmap
    from winrt.windows.storage.streams import InMemoryRandomAccessStream, DataWriter

    # Convert PIL Image to BMP bytes and load into WinRT
    buf = io.BytesIO()
    image.save(buf, format="BMP")
    bmp_bytes = buf.getvalue()

    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream)
    writer.write_bytes(bmp_bytes)
    await writer.store_async()
    await writer.flush_async()
    stream.seek(0)

    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()

    # Create OCR engine for the requested language
    language = Language(lang)
    engine = OcrEngine.try_create_from_language(language)
    if engine is None:
        # Fall back to user profile languages
        engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        return [], "OCR engine not available for language '%s'" % lang

    result = await engine.recognize_async(bitmap)

    words = []
    for line in result.lines:
        for word in line.words:
            bb = word.bounding_rect
            words.append({
                "text": word.text,
                "bounds": {
                    "x": int(bb.x),
                    "y": int(bb.y),
                    "width": int(bb.width),
                    "height": int(bb.height),
                },
            })

    full_text = result.text
    return words, full_text


def _run_ocr(image: Image.Image, lang: str = "en"):
    """Synchronous wrapper for async WinRT OCR."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_ocr_image_async(image, lang))
    finally:
        loop.close()


def ocr_region(x: int, y: int, w: int, h: int, lang: str = "en") -> dict:
    """OCR a screen region. Returns recognized text and word bounding boxes."""
    img = pyautogui.screenshot(region=(x, y, w, h))
    words, text = _run_ocr(img, lang)

    if isinstance(text, str) and not words and text.startswith("OCR engine"):
        return {"command": "ocr-region", "error": text}

    return {
        "command": "ocr-region",
        "region": {"x": x, "y": y, "width": w, "height": h},
        "text": text if isinstance(text, str) else "",
        "words": words if isinstance(words, list) else [],
        "word_count": len(words) if isinstance(words, list) else 0,
    }


def ocr_screen(lang: str = "en") -> dict:
    """OCR the entire active window."""
    import uiautomation as auto

    win = auto.GetForegroundControl()
    rect = win.BoundingRectangle
    x, y = rect.left, rect.top
    w = rect.right - rect.left
    h = rect.bottom - rect.top

    if w <= 0 or h <= 0:
        return {"command": "ocr-screen", "error": "Active window has no visible bounds"}

    img = pyautogui.screenshot(region=(x, y, w, h))
    words, text = _run_ocr(img, lang)

    if isinstance(text, str) and not words and text.startswith("OCR engine"):
        return {"command": "ocr-screen", "error": text}

    return {
        "command": "ocr-screen",
        "window": win.Name or "",
        "region": {"x": x, "y": y, "width": w, "height": h},
        "text": text if isinstance(text, str) else "",
        "words": words if isinstance(words, list) else [],
        "word_count": len(words) if isinstance(words, list) else 0,
    }
