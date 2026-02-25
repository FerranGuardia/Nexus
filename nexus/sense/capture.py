"""Screen capture abstraction — ScreenCaptureKit (macOS 14+) with CGWindowList fallback.

Provides window-level capture without stealing focus (ScreenCaptureKit),
region capture, and single-window capture by window ID.
"""

import platform
import io
import base64

from Quartz import (
    CGWindowListCreateImage,
    CGWindowListCopyWindowInfo,
    CGRectNull,
    CGRectMake,
    kCGWindowListOptionOnScreenOnly,
    kCGWindowListOptionIncludingWindow,
    kCGNullWindowID,
    kCGWindowImageDefault,
    kCGWindowImageBoundsIgnoreFraming,
    CGImageGetWidth,
    CGImageGetHeight,
    CGImageGetBytesPerRow,
    CGImageGetBitsPerPixel,
    CGImageGetDataProvider,
    CGDataProviderCopyData,
)
from PIL import Image


def _macos_version():
    """Get macOS major version as int."""
    try:
        ver = platform.mac_ver()[0]
        return int(ver.split(".")[0])
    except (ValueError, IndexError):
        return 0


def _has_screencapturekit():
    """Check if ScreenCaptureKit is available (macOS 14+)."""
    return _macos_version() >= 14


def capture_window(window_id):
    """Capture a specific window by its CGWindowID.

    Returns a PIL Image, or None on failure.
    Does NOT steal focus — uses kCGWindowListOptionIncludingWindow.
    """
    cg_image = CGWindowListCreateImage(
        CGRectNull,
        kCGWindowListOptionIncludingWindow,
        window_id,
        kCGWindowImageDefault | kCGWindowImageBoundsIgnoreFraming,
    )
    if not cg_image:
        return None
    return _cg_to_pil(cg_image)


def capture_region(x, y, w, h):
    """Capture a screen region.

    Returns a PIL Image, or None on failure.
    """
    rect = CGRectMake(x, y, w, h)
    cg_image = CGWindowListCreateImage(
        rect,
        kCGWindowListOptionOnScreenOnly,
        kCGNullWindowID,
        kCGWindowImageDefault,
    )
    if not cg_image:
        return None
    return _cg_to_pil(cg_image)


def capture_screen():
    """Capture the full screen.

    Returns a PIL Image, or None on failure.
    """
    cg_image = CGWindowListCreateImage(
        CGRectNull,
        kCGWindowListOptionOnScreenOnly,
        kCGNullWindowID,
        kCGWindowImageDefault,
    )
    if not cg_image:
        return None
    return _cg_to_pil(cg_image)


def capture_dialog(dialog):
    """Capture a system dialog by its bounds dict.

    Args:
        dialog: Dict with 'bounds' key containing {x, y, w, h}.
                Optionally 'window_id' for precise window capture.

    Returns a PIL Image, or None on failure.
    """
    # Try window_id first (more precise, captures the exact window)
    wid = dialog.get("window_id", 0)
    if wid:
        img = capture_window(wid)
        if img:
            return img

    # Fall back to region capture
    b = dialog.get("bounds", {})
    x, y, w, h = b.get("x", 0), b.get("y", 0), b.get("w", 0), b.get("h", 0)
    if w > 0 and h > 0:
        return capture_region(x, y, w, h)

    return None


def image_to_base64(img, max_width=1280, quality=70):
    """Convert PIL Image to base64 JPEG string.

    Resizes if wider than max_width for token efficiency.
    """
    if img is None:
        return None

    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    if img.mode == "RGBA":
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def image_to_file(img, path, max_width=1920, quality=85):
    """Save PIL Image to file. Returns the path."""
    if img is None:
        return None

    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    if img.mode == "RGBA":
        img = img.convert("RGB")

    img.save(path, quality=quality, optimize=True)
    return path


def _cg_to_pil(cg_image):
    """Convert a CGImage to a PIL Image."""
    width = CGImageGetWidth(cg_image)
    height = CGImageGetHeight(cg_image)
    bytes_per_row = CGImageGetBytesPerRow(cg_image)
    bpp = CGImageGetBitsPerPixel(cg_image)

    provider = CGImageGetDataProvider(cg_image)
    data = CGDataProviderCopyData(provider)

    if bpp == 32:
        img = Image.frombytes("RGBA", (width, height), bytes(data), "raw", "BGRA", bytes_per_row)
    else:
        img = Image.frombytes("RGB", (width, height), bytes(data), "raw", "BGR", bytes_per_row)

    return img
