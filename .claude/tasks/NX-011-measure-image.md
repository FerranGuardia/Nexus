# NX-011: Measure Image (Design-to-Code Reference Measurement)

**Branch:** `nexus-task`
**Status:** DONE
**Depends on:** NX-006 (Windows OCR), NX-010 (OmniParser)
**Tracking:** `.claude/tasks/INDEX.md`
**Started:** 2026-02-18
**Finished:** 2026-02-18

---

> **In plain English:** Given a design PNG (from Figma, Krita, etc.), detect all UI elements
> and measure their pixel-accurate bounds. Combines OmniParser (element detection) with
> Windows OCR (text recognition) to produce a structured element list.

---

## What Was Built

### Command: `measure-image`

```bash
python -m nexus measure-image C:\designs\hero.png
python -m nexus --format compact measure-image design.png --scale 0.5
```

### How It Works

1. Calls `vision_detect(image_path=...)` → OmniParser elements with bounds
2. Opens image with PIL, calls `_run_ocr()` → OCR words with bounds
3. Merges: OCR words whose center falls inside an OmniParser element get attached as `ocr_text`
4. Unclaimed OCR words are grouped into text runs (adjacent words within 6px vertical gap)
5. Scale factor applied to all coordinates (for @2x Figma exports)
6. Sorted by reading order (y-bucket then x), assigned ids `img_0`, `img_1`, ...

### Parameters

| Param | Default | Purpose |
|-------|---------|---------|
| `image_path` | required | Path to design PNG |
| `--threshold` | 0.05 | OmniParser detection confidence |
| `--iou` | 0.1 | Non-max suppression threshold |
| `--lang` | en | OCR language |
| `--scale` | 1.0 | Scale factor (0.5 for @2x exports) |

### Performance (Tested)

- Full-screen screenshot: 363 elements (342 OmniParser + 339 OCR words merged)
- Time: ~5-30s depending on GPU/CPU

### Files

- `nexus/oculus/image.py` — NEW: `measure_image()` + merge helpers
- `nexus/run.py` — CLI + daemon registration
- `nexus/mcp_server.py` — MCP tool
- `nexus/tools_schema.py` — description + category
- `nexus/format.py` — compact formatter
- `nexus/NEXUS-CONTEXT.md` — user docs
