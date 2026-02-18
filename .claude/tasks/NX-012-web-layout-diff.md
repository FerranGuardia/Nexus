# NX-012: Web Layout Diff (Design vs Live CSS Comparison)

**Branch:** `nexus-task`
**Status:** DONE
**Depends on:** NX-011 (Measure Image)
**Tracking:** `.claude/tasks/INDEX.md`
**Started:** 2026-02-18
**Finished:** 2026-02-18

---

> **In plain English:** Compare a reference design image against live CSS measurements
> in Chrome. Matches elements by text content (or position/index), computes per-element
> pixel deltas, and flags mismatches where dimensions differ by more than 10%.

---

## What Was Built

### Command: `web-layout-diff`

```bash
python -m nexus web-layout-diff C:\designs\hero.png ".hero, h1, .cta"
python -m nexus --format compact web-layout-diff design.png ".header, .body" --match-by position
```

### How It Works

1. Calls `measure_image(image_path)` → reference elements from design PNG
2. Calls `web_measure(selectors)` → live CSS measurements from Chrome
3. Extracts `innerText` for each selector via CDP
4. Matches elements using chosen strategy:
   - **text** (default): token overlap between OCR text and selector innerText
   - **position**: normalized 0-1 coords, nearest-neighbor
   - **index**: pair by sorted order
5. Computes per-pair deltas (width, height) with absolute and percentage diffs
6. Flags pairs where any dimension diff > 10% as `"ok": false`

### Parameters

| Param | Default | Purpose |
|-------|---------|---------|
| `image_path` | required | Reference design PNG |
| `selectors` | required | Comma-separated CSS selectors |
| `--tab` | 0 | Chrome tab index |
| `--port` | 9222 | Chrome CDP port |
| `--match-by` | text | Matching strategy: text, position, index |
| `--threshold` | 0.05 | OmniParser detection confidence |
| `--iou` | 0.1 | Non-max suppression threshold |
| `--lang` | en | OCR language |
| `--scale` | 1.0 | Scale factor for @2x exports |

### Compact Output Format

```
=== web-layout-diff: 8 matched, 2 issues ===
OK     .hero h1        ↔ img_3  W:640→620(-3.1%)  H:48→50(+4.2%)
MISMATCH .cta-button   ↔ img_7  W:200→280(+40.0%) H:48→48(+0.0%)
```

### Files

- `nexus/oculus/image.py` — `web_layout_diff()` + matching helpers
- `nexus/run.py` — CLI + daemon registration
- `nexus/mcp_server.py` — MCP tool
- `nexus/tools_schema.py` — description + category
- `nexus/format.py` — compact formatter
- `nexus/NEXUS-CONTEXT.md` — user docs + design-to-code workflow
