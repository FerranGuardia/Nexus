"""Perception plugins — pluggable fallback stack for see().

Each perception layer is a function: fn(pid, ctx) → [element_dicts]
Layers run in priority order. Later layers can be conditional on
what earlier layers found (e.g., OCR only when AX is sparse).

Element dicts from all layers are merged with a `source` tag
so do() can choose the right action method:
  - source="ax"       → AX actions (AXPress, AXConfirm), then coordinate fallback
  - source="ocr"      → coordinate click (center of text bounding box)
  - source="template" → coordinate click (pre-computed positions)

Adding a new perception layer is ~10 lines:
    from nexus.sense.plugins import register_layer
    def my_layer(pid, ctx):
        return [{"role": "button", "label": "Save", "pos": (x, y), ...}]
    register_layer("my_layer", my_layer, priority=70)
"""

import threading
import time

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_layers = []  # [(priority, name, handler, condition)]
_lock = threading.Lock()


def register_layer(name, handler, priority=50, condition=None):
    """Register a perception layer.

    Args:
        name: Layer name (e.g., "ax", "ocr", "template").
        handler: fn(pid, ctx) -> list of element dicts.
            ctx: {"pid", "elements" (from prior layers), "app_info", "bounds"}
        priority: Lower runs first (default 50).
        condition: Optional fn(ctx) -> bool. Layer skipped when False.
    """
    with _lock:
        _layers.append((priority, name, handler, condition))
        _layers.sort(key=lambda l: l[0])


def run_pipeline(pid, app_info=None, bounds=None, fetch_limit=150):
    """Run all perception layers and return merged elements.

    Args:
        pid: App PID.
        app_info: App info dict (name, pid, etc.).
        bounds: Window bounds (x, y, w, h) for OCR region.
        fetch_limit: Max elements for the AX layer.

    Returns:
        (elements, ctx) — elements is the merged list with source tags,
        ctx has side-channel data like tables/lists from the AX layer.
    """
    with _lock:
        layers = list(_layers)

    ctx = {
        "pid": pid,
        "elements": [],
        "app_info": app_info,
        "bounds": bounds,
        "fetch_limit": fetch_limit,
        "tables": [],
        "lists": [],
    }

    for _priority, name, handler, condition in layers:
        if condition is not None:
            try:
                if not condition(ctx):
                    continue
            except Exception:
                continue

        try:
            new_elements = handler(pid, ctx)
            if new_elements:
                for el in new_elements:
                    if "source" not in el:
                        el["source"] = name
                ctx["elements"].extend(new_elements)
        except Exception:
            pass  # Layers must never break the pipeline

    _cache_put(pid, ctx["elements"])
    return ctx["elements"], ctx


# ---------------------------------------------------------------------------
# Perception cache — most recent merged results per PID
# ---------------------------------------------------------------------------

_perception_cache = {}  # {pid: {"elements": [...], "ts": float}}
_PERCEPTION_TTL = 3.0
_MAX_CACHED_PIDS = 10


def _cache_get(pid):
    """Get cached perception elements for a PID."""
    if pid is None:
        return None
    with _lock:
        entry = _perception_cache.get(pid)
        if entry is None:
            return None
        if time.time() - entry["ts"] >= _PERCEPTION_TTL:
            return None
        return entry["elements"]


def _cache_put(pid, elements):
    """Store perception elements in cache."""
    if pid is None:
        return
    with _lock:
        _perception_cache[pid] = {
            "elements": list(elements),
            "ts": time.time(),
        }
        if len(_perception_cache) > _MAX_CACHED_PIDS:
            oldest = min(_perception_cache, key=lambda p: _perception_cache[p]["ts"])
            del _perception_cache[oldest]


def invalidate_cache(pid=None):
    """Clear perception cache (all PIDs or specific PID)."""
    with _lock:
        if pid is None:
            _perception_cache.clear()
        else:
            _perception_cache.pop(pid, None)


# ---------------------------------------------------------------------------
# Perception-aware element search
# ---------------------------------------------------------------------------

def perception_find(query, pid=None):
    """Search the perception cache for elements matching a query.

    Searches ALL perception sources (AX, OCR, template, etc.).
    Falls back to access.find_elements() if cache is empty/stale.

    Returns list of element dicts sorted by relevance score.
    """
    cached = _cache_get(pid)
    if cached is None:
        try:
            from nexus.sense.access import find_elements
            return find_elements(query, pid)
        except Exception:
            return []

    query_lower = query.lower().strip()
    matches = []
    for el in cached:
        label = (el.get("label") or "").lower()
        role = (el.get("role") or "").lower()
        value = (el.get("value") or "").lower()

        score = 0
        if query_lower == label:
            score = 100
        elif query_lower in label:
            score = 80
        elif label and label in query_lower:
            score = 60
        elif query_lower in f"{role} {label}":
            score = 50
        elif query_lower in value:
            score = 40

        # AX elements support richer actions — slight preference
        if score > 0 and el.get("source") == "ax":
            score += 5

        if score > 0:
            matches.append((score, el))

    matches.sort(key=lambda x: -x[0])
    return [el for _, el in matches]


def enrich_elements(ax_elements, pid):
    """Add non-AX elements from perception cache to an AX element list.

    Used by spatial/region click resolution to include OCR/template elements.
    Deduplicates by label to avoid double-matching.
    """
    cached = _cache_get(pid)
    if not cached:
        return ax_elements

    ax_labels = {(el.get("label") or "").lower() for el in ax_elements if el.get("label")}
    enriched = list(ax_elements)
    for el in cached:
        if el.get("source") != "ax" and (el.get("label") or "").lower() not in ax_labels:
            enriched.append(el)
    return enriched


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def registered_layers():
    """List registered layers for debugging."""
    with _lock:
        return [(p, n) for p, n, _, _ in _layers]


def clear():
    """Clear all layers and cache. For testing."""
    with _lock:
        _layers.clear()
        _perception_cache.clear()


# ---------------------------------------------------------------------------
# Built-in layers
# ---------------------------------------------------------------------------

def _ax_layer(pid, ctx):
    """Layer 1: Accessibility tree (always runs, ~200ms)."""
    from nexus.sense.access import full_describe
    fetch_limit = ctx.get("fetch_limit", 150)
    full = full_describe(pid, max_elements=fetch_limit)

    elements = full.get("elements", [])
    for el in elements:
        el["source"] = "ax"

    # Side-channel: tables and lists for fusion.py to render
    ctx["tables"] = full.get("tables", [])
    ctx["lists"] = full.get("lists", [])

    return elements


def _ocr_condition(ctx):
    """OCR layer runs when AX tree has <5 labeled elements."""
    elements = ctx.get("elements", [])
    labeled = sum(1 for el in elements if el.get("label"))
    return labeled < 5


def _ocr_layer(pid, ctx):
    """Layer 2: OCR fallback (when AX sparse, ~130ms)."""
    from nexus.sense.ocr import ocr_region, ocr_to_elements

    bounds = ctx.get("bounds")
    if not bounds:
        return []

    x, y, w, h = bounds
    if w <= 0 or h <= 0:
        return []

    ocr_results = ocr_region(x, y, w, h)
    if not ocr_results:
        return []

    return ocr_to_elements(ocr_results)


def _template_condition(ctx):
    """Template layer runs when system dialogs are detected."""
    try:
        from nexus.sense.system import detect_system_dialogs
        return bool(detect_system_dialogs())
    except Exception:
        return False


def _template_layer(pid, ctx):
    """Layer 3: Dialog templates (when known patterns found, ~50ms)."""
    from nexus.sense.system import detect_system_dialogs, classify_dialog
    from nexus.sense.templates import match_template, resolve_button, resolve_field

    elements = []
    dialogs = detect_system_dialogs()
    if not dialogs:
        return []

    # Get OCR elements already gathered by previous layers
    ocr_elements = [el for el in ctx.get("elements", []) if el.get("source") == "ocr"]

    for dialog in dialogs:
        db = dialog.get("bounds", {})

        # Build OCR text for this dialog's region
        dialog_ocr = [
            el for el in ocr_elements
            if _point_in_bounds(el.get("pos"), db)
        ]
        ocr_text = " ".join(el.get("label", "") for el in dialog_ocr)

        # If no OCR elements in region, try OCR on the dialog directly
        if not ocr_text.strip():
            try:
                from nexus.sense.ocr import ocr_region
                bx, by = db.get("x", 0), db.get("y", 0)
                bw, bh = db.get("w", 0), db.get("h", 0)
                if bw > 0 and bh > 0:
                    ocr_results = ocr_region(bx, by, bw, bh)
                    ocr_text = " ".join(r.get("text", "") for r in ocr_results)
            except Exception:
                pass

        template_id, template = match_template(ocr_text, dialog.get("process"))
        if not template:
            continue

        # Convert template buttons to clickable elements
        for btn_key, btn_info in template.get("buttons", {}).items():
            coords = resolve_button(template, btn_key, db)
            if coords:
                label = btn_info["labels"][0] if btn_info.get("labels") else btn_key
                elements.append({
                    "role": "button (template)",
                    "label": label,
                    "value": "",
                    "pos": (int(coords[0]), int(coords[1])),
                    "enabled": True,
                    "focused": False,
                    "source": "template",
                    "_template_id": template_id,
                })

        # Convert template fields to clickable elements
        for field_key in template.get("fields", {}):
            coords = resolve_field(template, field_key, db)
            if coords:
                elements.append({
                    "role": "field (template)",
                    "label": field_key,
                    "value": "",
                    "pos": (int(coords[0]), int(coords[1])),
                    "enabled": True,
                    "focused": False,
                    "source": "template",
                    "_template_id": template_id,
                })

    return elements


def _point_in_bounds(pos, bounds):
    """Check if a point (x, y) tuple falls within bounds dict."""
    if not pos or not bounds:
        return False
    px, py = pos
    bx = bounds.get("x", 0)
    by = bounds.get("y", 0)
    bw = bounds.get("w", 0)
    bh = bounds.get("h", 0)
    return bx <= px <= bx + bw and by <= py <= by + bh


def register_builtins():
    """Register the built-in perception layers. Safe to call multiple times."""
    with _lock:
        # Skip if already registered
        names = {n for _, n, _, _ in _layers}
        if "ax" in names:
            return

    register_layer("ax", _ax_layer, priority=10)
    register_layer("ocr", _ocr_layer, priority=50, condition=_ocr_condition)
    register_layer("template", _template_layer, priority=60, condition=_template_condition)


# Auto-register on import
register_builtins()
