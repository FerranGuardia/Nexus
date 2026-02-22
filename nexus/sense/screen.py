"""Screenshot capture for macOS via Quartz.

Takes screenshots of the full screen or specific windows.
Returns PIL Images or base64-encoded PNGs for MCP transport.
"""

import io
import base64
from Quartz import (
    CGWindowListCreateImage,
    CGRectNull,
    CGRectMake,
    kCGWindowListOptionOnScreenOnly,
    kCGNullWindowID,
    kCGWindowImageDefault,
    CGImageGetWidth,
    CGImageGetHeight,
    CGImageGetBytesPerRow,
    CGImageGetDataProvider,
    CGDataProviderCopyData,
    CGImageGetBitsPerPixel,
)
from PIL import Image


def capture_screen():
    """Capture the entire screen as a PIL Image."""
    cg_image = CGWindowListCreateImage(
        CGRectNull,  # Full screen
        kCGWindowListOptionOnScreenOnly,
        kCGNullWindowID,
        kCGWindowImageDefault,
    )
    if not cg_image:
        return None
    return _cg_to_pil(cg_image)


def capture_region(x, y, w, h):
    """Capture a specific screen region as a PIL Image."""
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


def _cg_to_pil(cg_image):
    """Convert a CGImage to a PIL Image."""
    width = CGImageGetWidth(cg_image)
    height = CGImageGetHeight(cg_image)
    bytes_per_row = CGImageGetBytesPerRow(cg_image)
    bpp = CGImageGetBitsPerPixel(cg_image)

    provider = CGImageGetDataProvider(cg_image)
    data = CGDataProviderCopyData(provider)

    # CGImage is typically BGRA on macOS
    if bpp == 32:
        img = Image.frombytes("RGBA", (width, height), bytes(data), "raw", "BGRA", bytes_per_row)
    else:
        img = Image.frombytes("RGB", (width, height), bytes(data), "raw", "BGR", bytes_per_row)

    return img


def screenshot_to_base64(img, max_width=1280, quality=70):
    """Compress a PIL Image and return base64 PNG.

    Resizes if wider than max_width to keep MCP payloads reasonable.
    """
    if img is None:
        return None

    # Downscale for token efficiency
    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    # Convert to RGB (drop alpha) for smaller size
    if img.mode == "RGBA":
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")
