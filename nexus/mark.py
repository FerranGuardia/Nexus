"""Set-of-Mark — numbered badge annotation for screenshots.

Draws numbered labels on screenshots at element positions so Claude can reference
elements by number instead of guessing coordinates. Returns the annotated image
path and a lookup table mapping numbers to element info.
"""

import os
import time

from PIL import Image, ImageDraw, ImageFont

SCREENSHOT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    ".tmp-screenshots",
)

# Badge appearance
BADGE_RADIUS = 12
BADGE_COLOR = (230, 60, 60)       # red
BADGE_TEXT_COLOR = (255, 255, 255) # white
BADGE_OUTLINE_COLOR = (255, 255, 255)


def _get_font(size: int = 14):
    """Get a font for badge numbers. Falls back to default if no TTF available."""
    try:
        return ImageFont.truetype("arial.ttf", size)
    except (IOError, OSError):
        try:
            return ImageFont.truetype("C:/Windows/Fonts/arial.ttf", size)
        except (IOError, OSError):
            return ImageFont.load_default()


def annotate_image(image: Image.Image, elements: list[dict]) -> tuple[Image.Image, list[dict]]:
    """Draw numbered badges on an image at each element's position.

    Args:
        image: PIL Image to annotate.
        elements: list of dicts, each with at minimum "bounds" containing {x, y, width, height}
                  and optionally "name", "type"/"role".

    Returns:
        (annotated_image, lookup_table) where lookup_table is a list of
        {"id": N, "name": ..., "role": ..., "x": center_x, "y": center_y, "bounds": {...}}
    """
    img = image.copy()
    draw = ImageDraw.Draw(img)
    font = _get_font(14)
    lookup = []

    for i, el in enumerate(elements):
        bounds = el.get("bounds", {})
        bx = bounds.get("x", bounds.get("left", 0))
        by = bounds.get("y", bounds.get("top", 0))
        bw = bounds.get("width", 0)
        bh = bounds.get("height", 0)

        if bw <= 0 or bh <= 0:
            continue

        mark_id = len(lookup) + 1

        # Position badge at top-left corner of element
        cx = bx + BADGE_RADIUS
        cy = by + BADGE_RADIUS

        # Clamp to image bounds
        cx = max(BADGE_RADIUS, min(cx, img.width - BADGE_RADIUS))
        cy = max(BADGE_RADIUS, min(cy, img.height - BADGE_RADIUS))

        # Draw badge circle with outline
        draw.ellipse(
            [cx - BADGE_RADIUS, cy - BADGE_RADIUS, cx + BADGE_RADIUS, cy + BADGE_RADIUS],
            fill=BADGE_COLOR,
            outline=BADGE_OUTLINE_COLOR,
            width=2,
        )

        # Draw number centered in badge
        label = str(mark_id)
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(
            (cx - tw // 2, cy - th // 2 - 1),
            label,
            fill=BADGE_TEXT_COLOR,
            font=font,
        )

        # Draw light rectangle around the element
        draw.rectangle(
            [bx, by, bx + bw, by + bh],
            outline=BADGE_COLOR,
            width=2,
        )

        # Build lookup entry
        entry = {
            "id": mark_id,
            "name": el.get("name", ""),
            "role": el.get("type", el.get("role", "")),
            "x": bx + bw // 2,
            "y": by + bh // 2,
            "bounds": {"x": bx, "y": by, "width": bw, "height": bh},
        }
        lookup.append(entry)

    return img, lookup


def screenshot_with_marks(elements: list[dict], region: str | None = None, full: bool = False) -> dict:
    """Take a screenshot with Set-of-Mark annotation.

    Args:
        elements: list of element dicts with bounds (from describe, web-ax, etc.)
        region: optional X,Y,W,H region string
        full: if True, skip downscaling

    Returns:
        {"command": "screenshot", "path": ..., "marks": [...lookup...], "mark_count": N}
    """
    import pyautogui

    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    if region:
        parts = tuple(int(x) for x in region.split(","))
        img = pyautogui.screenshot(region=parts)
    else:
        img = pyautogui.screenshot()

    if not full:
        # Downscale — need to scale element bounds too
        orig_w, orig_h = img.size
        target_w, target_h = 1920, 1080
        scale_x = target_w / orig_w
        scale_y = target_h / orig_h
        img = img.resize((target_w, target_h))

        # Scale element bounds
        scaled_elements = []
        for el in elements:
            bounds = el.get("bounds", {})
            scaled = dict(el)
            scaled["bounds"] = {
                "x": int(bounds.get("x", bounds.get("left", 0)) * scale_x),
                "y": int(bounds.get("y", bounds.get("top", 0)) * scale_y),
                "width": int(bounds.get("width", 0) * scale_x),
                "height": int(bounds.get("height", 0) * scale_y),
            }
            scaled_elements.append(scaled)
        elements = scaled_elements

    annotated, lookup = annotate_image(img, elements)

    filename = "nexus_mark_%d.png" % int(time.time() * 1000)
    filepath = os.path.join(SCREENSHOT_DIR, filename)
    annotated.save(filepath)

    return {
        "command": "screenshot",
        "path": filepath,
        "marks": lookup,
        "mark_count": len(lookup),
    }


# Module-level storage for last marks lookup (for click-mark)
_last_marks = []


def store_marks(marks: list[dict]):
    """Store the last marks lookup for click-mark resolution."""
    global _last_marks
    _last_marks = list(marks)


def resolve_mark(mark_id: int) -> dict | None:
    """Resolve a mark ID to its element info from the last marked screenshot."""
    for m in _last_marks:
        if m["id"] == mark_id:
            return m
    return None
