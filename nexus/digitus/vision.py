"""Digitus Vision — HTTP client for OmniParser element detection.

Sends screenshots to the OmniParser vision server and returns
structured UI elements in standard Nexus format.

Every function takes explicit typed params and returns a dict.
"""

import base64
import json
import os
import time
import urllib.request
import urllib.error

VISION_URL = os.environ.get("NEXUS_VISION_URL", "http://localhost:8500")

SCREENSHOT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".tmp-screenshots",
)


def vision_detect(
    image_path: str | None = None,
    region: str | None = None,
    box_threshold: float = 0.05,
    iou_threshold: float = 0.1,
    annotated: bool = False,
) -> dict:
    """Detect UI elements in a screenshot using OmniParser vision model.

    If image_path is None, takes a fresh screenshot first.
    Sends to OmniParser HTTP server, returns normalized elements.

    Args:
        image_path: Path to an image file. If None, takes a fresh screenshot.
        region: Screenshot region as "X,Y,W,H" (only used when image_path is None).
        box_threshold: Detection confidence threshold (lower = more detections).
        iou_threshold: IOU threshold for non-max suppression (overlap removal).
        annotated: If True, also save the annotated image with bounding boxes.
    """
    # Take screenshot if no image provided
    if image_path is None:
        from nexus.digitus.input import screenshot
        ss_result = screenshot(region=region)
        if "error" in ss_result:
            return {**ss_result, "command": "vision-detect"}
        image_path = ss_result["path"]

    # Read and base64-encode
    if not os.path.exists(image_path):
        return {
            "command": "vision-detect",
            "ok": False,
            "error": "Image not found: %s" % image_path,
        }

    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()

    # POST to vision server
    payload = json.dumps({
        "image": image_b64,
        "box_threshold": box_threshold,
        "iou_threshold": iou_threshold,
        "annotated": annotated,
    }).encode()

    url = VISION_URL.rstrip("/") + "/detect"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        return {
            "command": "vision-detect",
            "ok": False,
            "error": "OmniParser server unreachable at %s — %s" % (VISION_URL, e),
            "hint": "Start the server: cd omniparser-server && python server.py",
        }
    except Exception as e:
        return {
            "command": "vision-detect",
            "ok": False,
            "error": "Vision detection failed: %s" % e,
        }

    # Build result
    result = {
        "command": "vision-detect",
        "ok": data.get("ok", True),
        "elements": data.get("elements", []),
        "count": data.get("count", 0),
        "latency": data.get("latency"),
        "source_image": image_path,
    }

    # Save annotated image if returned
    if annotated and data.get("annotated_image"):
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        ann_path = os.path.join(
            SCREENSHOT_DIR, "vision_%d.png" % int(time.time() * 1000)
        )
        with open(ann_path, "wb") as f:
            f.write(base64.b64decode(data["annotated_image"]))
        result["annotated_path"] = ann_path

    return result


def vision_health() -> dict:
    """Check if the OmniParser vision server is running."""
    url = VISION_URL.rstrip("/") + "/health"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        return {"command": "vision-health", "ok": True, **data}
    except Exception as e:
        return {
            "command": "vision-health",
            "ok": False,
            "error": "Vision server unreachable at %s — %s" % (VISION_URL, e),
        }
