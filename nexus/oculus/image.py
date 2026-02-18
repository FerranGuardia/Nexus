"""Oculus Image — measure UI elements in design reference images.

Combines OmniParser (element detection) with WinRT OCR (text recognition) to
build a complete element map from exported design PNGs (Figma, Krita, etc.).

Also provides layout diffing: compare reference design measurements against
live CSS measurements from a browser page.

Pure functions: take params, return dict. No side effects beyond OmniParser HTTP calls.
"""

import math
import os
import time


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _ocr_image_file(image_path: str, lang: str = "en"):
    """Run WinRT OCR on an image file. Returns (words, full_text)."""
    from PIL import Image
    from nexus.oculus.ocr import _run_ocr

    img = Image.open(image_path).convert("RGB")
    return _run_ocr(img, lang)


def _point_in_bounds(px: int, py: int, bounds: dict, tolerance: int = 2) -> bool:
    """Check if a point (px, py) falls inside bounds with tolerance."""
    x = bounds.get("x", 0) - tolerance
    y = bounds.get("y", 0) - tolerance
    x2 = x + bounds.get("width", 0) + 2 * tolerance
    y2 = y + bounds.get("height", 0) + 2 * tolerance
    return x <= px <= x2 and y <= py <= y2


def _merge_omniparser_ocr(vision_elements: list, ocr_words: list, scale: float) -> list:
    """Merge OmniParser elements with OCR words via containment.

    - OCR words whose center falls inside an OmniParser element get attached as ocr_text.
    - Remaining OCR words are grouped into text runs and become standalone elements.
    - Scale factor is applied to all coordinates.
    """
    # Track which OCR words are claimed by OmniParser elements
    claimed = [False] * len(ocr_words)

    # For each OmniParser element, collect OCR words inside it
    element_ocr = {i: [] for i in range(len(vision_elements))}
    for wi, word in enumerate(ocr_words):
        wb = word.get("bounds", {})
        wcx = wb.get("x", 0) + wb.get("width", 0) // 2
        wcy = wb.get("y", 0) + wb.get("height", 0) // 2

        for ei, el in enumerate(vision_elements):
            if _point_in_bounds(wcx, wcy, el.get("bounds", {})):
                element_ocr[ei].append(word)
                claimed[wi] = True
                break

    # Build merged elements from OmniParser + claimed OCR words
    merged = []
    for i, el in enumerate(vision_elements):
        entry = {
            "name": el.get("name", ""),
            "type": el.get("type", "unknown"),
            "bounds": dict(el.get("bounds", {})),
            "source": "omniparser",
        }
        words = element_ocr[i]
        if words:
            # Sort words left-to-right within the element
            words.sort(key=lambda w: w["bounds"]["x"])
            entry["ocr_text"] = " ".join(w["text"] for w in words)
            entry["source"] = "omniparser+ocr"
        merged.append(entry)

    # Group unclaimed OCR words into text runs
    unclaimed = [ocr_words[i] for i in range(len(ocr_words)) if not claimed[i]]
    if unclaimed:
        runs = _group_ocr_words(unclaimed)
        for run in runs:
            merged.append(run)

    # Apply scale factor
    if scale != 1.0:
        for el in merged:
            b = el.get("bounds", {})
            for key in ("x", "y", "width", "height", "center_x", "center_y"):
                if key in b:
                    b[key] = int(b[key] * scale)

    # Ensure center_x/center_y exist
    for el in merged:
        b = el.get("bounds", {})
        if "center_x" not in b:
            b["center_x"] = b.get("x", 0) + b.get("width", 0) // 2
        if "center_y" not in b:
            b["center_y"] = b.get("y", 0) + b.get("height", 0) // 2

    # Sort by reading order: row bucket (y // 20) then x
    merged.sort(key=lambda el: (el["bounds"].get("y", 0) // 20, el["bounds"].get("x", 0)))

    # Assign sequential IDs
    for i, el in enumerate(merged):
        el["id"] = "img_%d" % i

    return merged


def _group_ocr_words(words: list) -> list:
    """Group OCR words into text runs based on spatial proximity.

    Words within 6px vertically and reasonable x-gap get merged into one element.
    """
    if not words:
        return []

    # Sort by y then x
    words.sort(key=lambda w: (w["bounds"]["y"], w["bounds"]["x"]))

    runs = []
    current_run = [words[0]]

    for w in words[1:]:
        prev = current_run[-1]
        pb = prev["bounds"]
        wb = w["bounds"]

        # Same row: y-centers within 6px and x-gap reasonable
        prev_cy = pb["y"] + pb["height"] // 2
        curr_cy = wb["y"] + wb["height"] // 2
        x_gap = wb["x"] - (pb["x"] + pb["width"])

        if abs(prev_cy - curr_cy) <= 6 and x_gap < max(pb["width"], 20):
            current_run.append(w)
        else:
            runs.append(_run_to_element(current_run))
            current_run = [w]

    if current_run:
        runs.append(_run_to_element(current_run))

    return runs


def _run_to_element(words: list) -> dict:
    """Convert a list of OCR words into a single text element."""
    text = " ".join(w["text"] for w in words)
    # Compute bounding box encompassing all words
    x_min = min(w["bounds"]["x"] for w in words)
    y_min = min(w["bounds"]["y"] for w in words)
    x_max = max(w["bounds"]["x"] + w["bounds"]["width"] for w in words)
    y_max = max(w["bounds"]["y"] + w["bounds"]["height"] for w in words)
    w = x_max - x_min
    h = y_max - y_min

    return {
        "name": text,
        "ocr_text": text,
        "type": "text",
        "bounds": {
            "x": x_min,
            "y": y_min,
            "width": w,
            "height": h,
            "center_x": x_min + w // 2,
            "center_y": y_min + h // 2,
        },
        "source": "ocr",
    }


def _token_overlap(a: str, b: str) -> float:
    """Compute token overlap score between two strings. Returns 0-1."""
    if not a or not b:
        return 0.0
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    common = tokens_a & tokens_b
    return len(common) / max(len(tokens_a), len(tokens_b))


def _match_by_text(image_elements: list, selector_texts: list, selectors: list):
    """Match image elements to selectors by text content overlap."""
    matched = []
    unmatched_sels = []
    used_image_ids = set()

    # Build score matrix
    scores = []
    for si, sel_text in enumerate(selector_texts):
        if not sel_text:
            continue
        for ei, el in enumerate(image_elements):
            el_text = el.get("ocr_text", "") or el.get("name", "")
            score = _token_overlap(sel_text, el_text)
            if score >= 0.4:
                scores.append((score, si, ei))

    # Greedy: take highest score pairs
    scores.sort(reverse=True)
    matched_sels = set()
    for score, si, ei in scores:
        eid = image_elements[ei].get("id", "")
        if si in matched_sels or eid in used_image_ids:
            continue
        matched.append({
            "selector": selectors[si],
            "image_id": eid,
            "image_text": image_elements[ei].get("ocr_text", "") or image_elements[ei].get("name", ""),
            "live_text": selector_texts[si],
            "match_score": round(score, 2),
            "image_bounds": image_elements[ei].get("bounds", {}),
        })
        matched_sels.add(si)
        used_image_ids.add(eid)

    for si, sel in enumerate(selectors):
        if si not in matched_sels:
            unmatched_sels.append(sel)

    unmatched_img = [el["id"] for el in image_elements if el.get("id") not in used_image_ids]
    return matched, unmatched_sels, unmatched_img


def _match_by_position(image_elements: list, web_elements: list, selectors: list,
                        img_w: int, img_h: int, vp_w: int, vp_h: int):
    """Match by normalized position (nearest-neighbor in 0-1 space)."""
    matched = []
    used_image_ids = set()

    for si, web_el in enumerate(web_elements):
        if web_el.get("error"):
            continue
        # Normalize web element center
        wcx = (web_el.get("x", 0) + web_el.get("width", 0) / 2) / max(vp_w, 1)
        wcy = (web_el.get("y", 0) + web_el.get("height", 0) / 2) / max(vp_h, 1)

        best_dist = float("inf")
        best_ei = -1
        for ei, img_el in enumerate(image_elements):
            eid = img_el.get("id", "")
            if eid in used_image_ids:
                continue
            b = img_el.get("bounds", {})
            icx = b.get("center_x", 0) / max(img_w, 1)
            icy = b.get("center_y", 0) / max(img_h, 1)
            dist = math.sqrt((wcx - icx) ** 2 + (wcy - icy) ** 2)
            if dist < best_dist:
                best_dist = dist
                best_ei = ei

        if best_ei >= 0:
            el = image_elements[best_ei]
            matched.append({
                "selector": selectors[si],
                "image_id": el.get("id", ""),
                "image_text": el.get("ocr_text", "") or el.get("name", ""),
                "match_score": round(max(0, 1.0 - best_dist), 2),
                "image_bounds": el.get("bounds", {}),
            })
            used_image_ids.add(el.get("id", ""))

    unmatched_sels = [selectors[si] for si, web_el in enumerate(web_elements)
                      if web_el.get("error") or selectors[si] not in [m["selector"] for m in matched]]
    unmatched_img = [el["id"] for el in image_elements if el.get("id") not in used_image_ids]
    return matched, unmatched_sels, unmatched_img


def _match_by_index(image_elements: list, selectors: list):
    """Match by list position: 1st selector = 1st image element (sorted by y,x)."""
    matched = []
    n = min(len(image_elements), len(selectors))
    for i in range(n):
        el = image_elements[i]
        matched.append({
            "selector": selectors[i],
            "image_id": el.get("id", ""),
            "image_text": el.get("ocr_text", "") or el.get("name", ""),
            "match_score": 1.0,
            "image_bounds": el.get("bounds", {}),
        })
    unmatched_sels = selectors[n:]
    unmatched_img = [el["id"] for el in image_elements[n:]]
    return matched, unmatched_sels, unmatched_img


def _compute_deltas(image_bounds: dict, web_el: dict) -> dict:
    """Compute per-dimension deltas between image element and live CSS element."""
    deltas = {}
    for dim in ("width", "height"):
        img_val = image_bounds.get(dim, 0)
        live_val = web_el.get(dim, 0)
        diff = live_val - img_val
        diff_pct = round(diff / img_val * 100, 1) if img_val else 0
        deltas[dim] = {"image": img_val, "live": live_val, "diff": diff, "diff_pct": diff_pct}

    for dim in ("x", "y"):
        img_val = image_bounds.get(dim, 0)
        live_val = web_el.get(dim, 0)
        deltas[dim] = {"image": img_val, "live": live_val, "diff": live_val - img_val}

    return deltas


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def measure_image(
    image_path: str,
    box_threshold: float = 0.05,
    iou_threshold: float = 0.1,
    lang: str = "en",
    scale: float = 1.0,
) -> dict:
    """Measure UI elements in a reference design image (OmniParser + OCR).

    Combines vision detection (icons/elements) with text recognition to build
    a complete element map of a design PNG exported from Figma or Krita.

    Args:
        image_path: Absolute path to PNG image.
        box_threshold: OmniParser confidence threshold (default 0.05).
        iou_threshold: OmniParser overlap threshold (default 0.1).
        lang: OCR language (default "en").
        scale: Scale factor for @2x exports — 0.5 halves all coordinates.
    """
    if not os.path.isfile(image_path):
        return {"command": "measure-image", "ok": False, "error": "File not found: %s" % image_path}

    t0 = time.time()

    # Step 1: OmniParser element detection
    from nexus.digitus.vision import vision_detect
    vision_result = vision_detect(
        image_path=image_path,
        box_threshold=box_threshold,
        iou_threshold=iou_threshold,
    )
    if not vision_result.get("ok"):
        return {"command": "measure-image", "ok": False, "error": vision_result.get("error", "OmniParser failed")}

    vision_elements = vision_result.get("elements", [])
    omniparser_count = len(vision_elements)

    # Step 2: WinRT OCR for text recognition
    ocr_words, ocr_text = _ocr_image_file(image_path, lang)
    if isinstance(ocr_text, str) and ocr_text.startswith("OCR engine"):
        # OCR unavailable — proceed with OmniParser results only
        ocr_words = []
    ocr_word_count = len(ocr_words) if isinstance(ocr_words, list) else 0

    # Step 3: Merge OmniParser + OCR
    merged = _merge_omniparser_ocr(vision_elements, ocr_words if isinstance(ocr_words, list) else [], scale)

    # Get image dimensions
    from PIL import Image
    img = Image.open(image_path)
    img_w, img_h = img.size
    if scale != 1.0:
        img_w = int(img_w * scale)
        img_h = int(img_h * scale)

    latency = time.time() - t0

    return {
        "command": "measure-image",
        "ok": True,
        "image_path": image_path,
        "image_size": {"width": img_w, "height": img_h},
        "scale": scale,
        "elements": merged,
        "count": len(merged),
        "omniparser_count": omniparser_count,
        "ocr_word_count": ocr_word_count,
        "latency": round(latency, 3),
    }


def web_layout_diff(
    image_path: str,
    selectors: str,
    tab: int = 0,
    port: int = 9222,
    box_threshold: float = 0.05,
    iou_threshold: float = 0.1,
    lang: str = "en",
    scale: float = 1.0,
    match_by: str = "text",
) -> dict:
    """Compare a reference design image against live CSS measurements.

    Runs measure-image on the PNG, runs web-measure on the selectors,
    matches elements, and returns per-element pixel deltas.

    Args:
        image_path: Absolute path to reference design PNG.
        selectors: Comma-separated CSS selectors (e.g. ".hero, h1, .btn").
        tab: Target tab index.
        port: CDP port (default 9222).
        box_threshold: OmniParser confidence threshold.
        iou_threshold: OmniParser overlap threshold.
        lang: OCR language.
        scale: Scale factor for @2x exports.
        match_by: Matching strategy — "text" (default), "position", or "index".
    """
    # Step 1: Measure reference image
    img_result = measure_image(
        image_path=image_path,
        box_threshold=box_threshold,
        iou_threshold=iou_threshold,
        lang=lang,
        scale=scale,
    )
    if not img_result.get("ok"):
        return {"command": "web-layout-diff", "ok": False, "error": img_result.get("error", "measure-image failed")}

    image_elements = img_result.get("elements", [])
    img_size = img_result.get("image_size", {})

    # Step 2: Measure live page
    from nexus.oculus.web import web_measure
    web_result = web_measure(selectors=selectors, tab=tab, port=port)
    if not web_result.get("ok", True):
        return {"command": "web-layout-diff", "ok": False, "error": web_result.get("error", "web-measure failed")}

    web_elements = web_result.get("elements", [])
    selector_list = [el.get("selector", "") for el in web_elements]

    # Step 3: Extract innerText for each selector (for text matching)
    selector_texts = []
    if match_by == "text":
        from nexus.cdp import cdp_page
        with cdp_page("http://localhost:%d" % port) as page:
            js = """(sels) => sels.map(sel => {
                const el = document.querySelector(sel);
                return el ? el.innerText.trim().substring(0, 200) : null;
            })"""
            selector_texts = page.evaluate(js, selector_list)
    else:
        selector_texts = [None] * len(selector_list)

    # Step 4: Match elements
    if match_by == "text":
        matched, unmatched_sels, unmatched_img = _match_by_text(
            image_elements, selector_texts, selector_list,
        )
    elif match_by == "position":
        # Get viewport size for normalization
        vp_w = max(el.get("x", 0) + el.get("width", 0) for el in web_elements) if web_elements else 1920
        vp_h = max(el.get("y", 0) + el.get("height", 0) for el in web_elements) if web_elements else 1080
        matched, unmatched_sels, unmatched_img = _match_by_position(
            image_elements, web_elements, selector_list,
            img_size.get("width", 1), img_size.get("height", 1), vp_w, vp_h,
        )
    elif match_by == "index":
        matched, unmatched_sels, unmatched_img = _match_by_index(
            image_elements, selector_list,
        )
    else:
        return {"command": "web-layout-diff", "ok": False, "error": "Unknown match_by: %s" % match_by}

    # Step 5: Compute deltas for matched pairs
    web_by_selector = {el.get("selector", ""): el for el in web_elements}
    issues = 0
    for m in matched:
        sel = m["selector"]
        web_el = web_by_selector.get(sel, {})
        if web_el.get("error"):
            m["deltas"] = {}
            m["ok"] = False
            m["error"] = web_el["error"]
            issues += 1
            continue

        deltas = _compute_deltas(m["image_bounds"], web_el)
        m["deltas"] = deltas

        # Include CSS properties from web-measure
        m["css"] = {
            "font_size": web_el.get("font_size"),
            "padding": web_el.get("padding"),
            "margin": web_el.get("margin"),
            "display": web_el.get("display"),
        }

        # Flag if any dimension diff > 10%
        ok = True
        for dim in ("width", "height"):
            if abs(deltas.get(dim, {}).get("diff_pct", 0)) > 10:
                ok = False
                break
        m["ok"] = ok
        if not ok:
            issues += 1

        # Clean up internal field
        del m["image_bounds"]

    return {
        "command": "web-layout-diff",
        "ok": True,
        "image_path": image_path,
        "url": web_result.get("url", ""),
        "match_by": match_by,
        "matched": matched,
        "unmatched_selectors": unmatched_sels,
        "unmatched_image_elements": unmatched_img,
        "summary": {
            "matched": len(matched),
            "unmatched_selectors": len(unmatched_sels),
            "unmatched_image_elements": len(unmatched_img),
            "issues": issues,
        },
    }
