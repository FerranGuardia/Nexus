# NX-010: OmniParser Integration (Vision-Based Element Detection)

**Branch:** `nexus-task`
**Status:** DONE
**Depends on:** None (enhanced by NX-007 Set-of-Mark)
**Tracking:** `.claude/tasks/INDEX.md`
**Started:** 2026-02-18
**Finished:** 2026-02-18

---

> **In plain English:** Some apps have no accessibility tree at all — custom-rendered UIs, games,
> canvas elements. OmniParser uses vision models (YOLO + Florence-2) to detect UI elements
> from screenshots, giving Nexus structured element data where UIA fails.

---

## What Was Built

### Architecture: HTTP Sidecar (separate process, separate venv)

OmniParser runs as its own service — not embedded in Nexus. Reasons:
- Heavy deps (PyTorch, transformers, YOLO — ~4-5 GB) shouldn't pollute Nexus's venv
- User is getting a Mac next week — Nexus client stays platform-agnostic, server can be adapted per platform
- Same pattern as Edge TTS sidecar

```
omniparser-server/       # Separate service (own venv, own process)
  server.py              # FastAPI on :8500, wraps OmniParser V2
  omni_utils.py          # Import shim: stubs paddleocr, re-exports OmniParser utils
  setup.py               # Clones OmniParser repo (--depth 1)
  download_models.py     # Downloads YOLO (~40MB) + Florence-2 (~1.08GB) from HuggingFace
  requirements.txt       # Pinned deps (transformers==4.45.2 critical)
  models/
    icon_detect/model.pt # YOLO v8
    icon_caption/         # Florence-2 fine-tuned weights
    florence2_base/       # Florence-2 processor files (patched locally)

nexus/digitus/vision.py  # HTTP client — pure function, urllib only
```

### Commands Added

| Command | Interface | What it does |
|---------|-----------|-------------|
| `vision-detect` | CLI + MCP | Screenshot → base64 → POST to server → structured elements |
| `vision-health` | CLI + MCP | Check if OmniParser server is alive |

### Key Design Decisions

1. **Local processor loading**: Florence-2 processor loaded from `models/florence2_base/` (patched locally) instead of downloading latest from HuggingFace. The HF-hosted `processing_florence2.py` is incompatible with `tokenizers>=0.20`.

2. **`transformers==4.45.2` pinned**: Newer versions break Florence-2's dynamic model code. Must also clear HF module cache at `~/.cache/huggingface/modules/transformers_modules/microsoft/Florence*` if switching versions.

3. **paddleocr stubbed**: OmniParser imports paddleocr at module level but we use `easyocr` with `use_paddleocr=False`. Stubbing saves ~500MB install.

4. **60s timeout**: Vision inference can be slow on CPU. Client uses 60s timeout.

5. **`NEXUS_VISION_URL` env var**: Defaults to `http://localhost:8500`. Override for remote server.

### Performance (Tested)

- **GPU (RTX)**: ~26s first call (model warmup), ~1-5s subsequent
- **Elements detected**: 450 from full screen (231 text + 219 icons)
- **Output format**: Standard Nexus element format — `{id, name, type, bounds: {x, y, width, height, center_x, center_y}, interactivity, source}`

### Files Modified

- `nexus/digitus/vision.py` — NEW: HTTP client (urllib, base64)
- `nexus/run.py` — Added vision-detect, vision-health to CLI + daemon command tables
- `nexus/mcp_server.py` — Added vision_detect, vision_health MCP tools (with annotated image support)
- `nexus/tools_schema.py` — Added Vision category + descriptions
- `nexus/NEXUS-CONTEXT.md` — Added vision section with usage guidance
- `.gitignore` — Added omniparser-server/.venv/, OmniParser/, models/
- `omniparser-server/*` — All new (server, setup, download, README)

## Not in Scope (Future)

- `vision-describe` (hybrid UIA + OmniParser with IoU deduplication) — planned but not needed yet
- Training custom models
- Real-time vision / video analysis
- ShowUI or other VLA models
