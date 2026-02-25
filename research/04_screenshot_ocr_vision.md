# Research: Screenshot, OCR & Vision Approaches for macOS Automation

**Date:** 2026-02-24
**Context:** Nexus currently relies on the macOS Accessibility API (AXUIElement) for UI perception. When the AX tree is empty or unavailable (system dialogs, some Electron apps, Gatekeeper prompts), Nexus is blind. This document researches screenshot-based, OCR-based, and vision-model-based fallback strategies.

---

## Table of Contents

1. [macOS Screenshot APIs](#1-macos-screenshot-apis)
2. [OCR on macOS](#2-ocr-on-macos)
3. [Screenshot + Coordinate Clicking Approaches](#3-screenshot--coordinate-clicking-approaches)
4. [Efficient Screenshot Transport](#4-efficient-screenshot-transport)
5. [Vision Models for UI Understanding](#5-vision-models-for-ui-understanding)
6. [Hybrid Approaches](#6-hybrid-approaches)
7. [Relevant GitHub Repos](#7-relevant-github-repos)
8. [Recommendations for Nexus](#8-recommendations-for-nexus)

---

## 1. macOS Screenshot APIs

### 1.1 CGWindowListCreateImage (Legacy, Deprecated in macOS 15)

**What it does:** Returns a composite CGImage based on a dynamically generated list of windows.

**API:**
```python
from Quartz import (
    CGWindowListCreateImage, CGRectNull,
    kCGWindowListOptionOnScreenOnly,
    kCGWindowListOptionIncludingWindow,
    kCGNullWindowID, kCGWindowImageDefault,
)

# Full screen capture
cg_image = CGWindowListCreateImage(
    CGRectNull,
    kCGWindowListOptionOnScreenOnly,
    kCGNullWindowID,
    kCGWindowImageDefault,
)

# Single window by ID
cg_image = CGWindowListCreateImage(
    CGRectNull,  # Use window's own bounds
    kCGWindowListOptionIncludingWindow,
    window_id,   # CGWindowID (int)
    kCGWindowImageDefault,
)
```

**Key capabilities:**
- Capture full screen, specific region (`CGRectMake(x,y,w,h)`), or single window by ID
- `kCGWindowListOptionIncludingWindow` captures one window by its `kCGWindowNumber`
- `kCGWindowImageBoundsIgnoreFraming` to capture without shadow/frame
- Window IDs obtained from `CGWindowListCopyWindowInfo()`

**Can it capture system dialogs?** Partially. CGWindowListCreateImage captures composited screen content, so it can capture what's visually visible, including system dialogs from CoreServicesUIAgent/SecurityAgent. However, you're capturing the screen's visual buffer, not the dialog's AX tree. If you know the window bounds (from `CGWindowListCopyWindowInfo`), you can capture the dialog's image.

**Limitations:**
- **DEPRECATED in macOS 15.0 (Sequoia).** Apple recommends ScreenCaptureKit.
- Requires Screen Recording permission (TCC)
- Without permission, returns empty screenshot (no windows visible)
- Performance: ~7 fps in benchmarks, significantly worse than ScreenCaptureKit
- Higher CPU usage than ScreenCaptureKit

**Nexus relevance:** Nexus already uses this in `nexus/sense/screen.py`. Works on macOS <15 but needs migration path.

**References:**
- https://developer.apple.com/documentation/coregraphics/1454852-cgwindowlistcreateimage
- https://developer.apple.com/documentation/coregraphics/1455137-cgwindowlistcopywindowinfo

### 1.2 CGWindowListCreateImageFromArray

**What it does:** Creates a composite image from a specific set of windows defined by an array of window IDs.

**API:**
```python
from Quartz import CGWindowListCreateImageFromArray

# Capture specific windows composited together
cg_image = CGWindowListCreateImageFromArray(
    CGRectNull,      # Use combined bounds of all windows
    window_id_array, # CFArray of CGWindowIDs
    kCGWindowImageDefault,
)
```

**Key capabilities:**
- Capture multiple specific windows composited in a defined order
- Useful for capturing a dialog overlaying an app window

**Limitations:** Same deprecation as CGWindowListCreateImage.

**References:**
- https://developer.apple.com/documentation/coregraphics/1455730-cgwindowlistcreateimagefromarray

### 1.3 screencapture CLI Tool

**What it does:** macOS built-in command-line screenshot tool.

**Key flags:**
| Flag | Purpose |
|------|---------|
| `-x` | No sound |
| `-l <windowID>` | **Capture specific window by CGWindowID** |
| `-R <x,y,w,h>` | Capture specific screen region (undocumented in man page, shown in `-h`) |
| `-t <format>` | Image format: png (default), jpg, tiff, pdf |
| `-w` | Window selection mode only |
| `-W` | Start in window selection mode |
| `-c` | Capture to clipboard |
| `-o` | No window shadow |
| `-C` | Include cursor |
| `-T <seconds>` | Delay before capture |
| `-i` | Interactive (space toggles selection/window mode) |

**The `-l` flag is the key feature:** `screencapture -x -l <windowID> /tmp/shot.png` captures a specific window without user interaction. This is what Nexus currently can use for targeted window capture without needing to implement CGImage conversion.

**Getting window IDs:**
```python
from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID

windows = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
for w in windows:
    print(w['kCGWindowNumber'], w.get('kCGWindowOwnerName', ''), w.get('kCGWindowName', ''))
```

**Can it capture system dialogs?** Yes, if you know the window ID. CoreServicesUIAgent windows appear in `CGWindowListCopyWindowInfo`.

**Speed:** Slower than in-process API calls (~200-500ms round trip due to process spawn + file I/O).

**References:**
- https://ss64.com/mac/screencapture.html
- https://github.com/smokris/GetWindowID

### 1.4 ScreenCaptureKit (macOS 12.3+, the modern API)

**What it does:** Apple's modern framework for screen/window/app capture. Replaces CGWindowListCreateImage.

**Key classes:**
- `SCShareableContent` -- enumerates available displays, windows, applications
- `SCWindow` -- represents an onscreen window (ID, frame, title, on-screen state)
- `SCContentFilter` -- defines what to capture (single window, app, display)
- `SCStreamConfiguration` -- output format, resolution, color space, cursor visibility
- `SCScreenshotManager` -- single-frame capture (class methods, no instantiation needed)
- `SCStream` -- continuous streaming capture

**Single window capture flow:**
1. Get shareable content via `SCShareableContent.getShareableContentWithCompletionHandler_`
2. Find the target `SCWindow` by matching windowID
3. Create `SCContentFilter` with `desktopIndependentWindow` type
4. Configure `SCStreamConfiguration` (resolution, pixel format, etc.)
5. Call `SCScreenshotManager.captureImage(contentFilter:configuration:completionHandler:)`

**PyObjC bindings:**
```python
# pip install pyobjc-framework-ScreenCaptureKit
from ScreenCaptureKit import (
    SCContentFilter, SCScreenshotManager,
    SCStreamConfiguration, SCShareableContent,
)
```

**Performance:** ~60 fps capture (vs ~7 fps for CGWindowListCreateImage). CPU usage cut by up to half. Significantly lower latency.

**Limitations:**
- macOS 12.3+ required
- Requires Screen Recording permission (TCC) -- same as CGWindowListCreateImage
- Async/callback-based API -- awkward in synchronous Python code (need CFRunLoop or threading)
- `SCScreenshotManager` is macOS 14+ (Sonoma) -- earlier versions need SCStream for single frames
- PyObjC bindings exist but documentation/examples are sparse
- Known issue: pyobjc issue #590 discusses difficulties with the async callback pattern

**Workaround for synchronous capture (pyobjc):**
The pyobjc issue #590 poster ultimately fell back to a simpler Quartz approach:
```python
from Quartz import CGDisplayCreateImage, CGMainDisplayID

# Full display capture (synchronous, simple)
screenshot = CGDisplayCreateImage(CGMainDisplayID())
```

**Can it capture system dialogs?** Yes, SCShareableContent enumerates all windows including system ones. You can filter to capture specific CoreServicesUIAgent windows.

**References:**
- https://developer.apple.com/documentation/screencapturekit/
- https://developer.apple.com/documentation/screencapturekit/scwindow
- https://developer.apple.com/videos/play/wwdc2022/10156/
- https://nonstrict.eu/blog/2023/a-look-at-screencapturekit-on-macos-sonoma/
- https://github.com/ronaldoussoren/pyobjc/issues/590
- https://pypi.org/project/pyobjc-framework-ScreenCaptureKit/

### 1.5 Summary: Screenshot API Comparison

| Feature | CGWindowListCreateImage | screencapture CLI | ScreenCaptureKit |
|---------|------------------------|-------------------|------------------|
| Min macOS | 10.5 | 10.0 | 12.3 |
| Deprecated? | **Yes (macOS 15)** | No | No (recommended) |
| Single window | Yes (by windowID) | Yes (`-l` flag) | Yes (SCContentFilter) |
| Region capture | Yes (CGRect) | Yes (`-R` flag) | Yes (configuration) |
| System dialogs | Yes (visual) | Yes (`-l` + windowID) | Yes (SCWindow) |
| Speed | ~7 fps, high CPU | ~200-500ms (process spawn) | ~60 fps, low CPU |
| Sync Python | Easy | Easy (subprocess) | Hard (async callbacks) |
| Permission | Screen Recording | Screen Recording | Screen Recording |
| Nexus status | **Currently used** | Easy to adopt | Needs migration work |

**Recommendation:** For immediate use, `screencapture -x -l <windowID>` for targeted window capture. For the future, migrate to ScreenCaptureKit for performance. Keep CGWindowListCreateImage as fallback on older macOS.

---

## 2. OCR on macOS

### 2.1 Apple Vision Framework (VNRecognizeTextRequest)

**What it does:** On-device text recognition using Apple's neural network models. Ships with macOS 10.15+.

**Python access via pyobjc:**
```python
import Vision
from Quartz import CIImage
from Foundation import NSURL, NSDictionary

# Load image
url = NSURL.fileURLWithPath_("/tmp/screenshot.png")
ci_image = CIImage.imageWithContentsOfURL_(url)

# Create request
request = Vision.VNRecognizeTextRequest.alloc().init()
request.setRecognitionLevel_(0)  # 0 = accurate, 1 = fast

# Process
handler = Vision.VNImageRequestHandler.alloc().initWithCIImage_options_(ci_image, None)
success, error = handler.performRequests_error_([request], None)

# Extract results
for observation in request.results():
    candidate = observation.topCandidates_(1)[0]
    text = candidate.string()
    confidence = candidate.confidence()
    bbox = observation.boundingBox()  # Normalized coords (origin bottom-left)
    # bbox: (x, y, width, height) where 0,0 = bottom-left
```

**Recognition modes:**
- **Accurate** (level 0): 207ms per image (M3 Max). Better accuracy, especially for complex layouts.
- **Fast** (level 1): 131ms per image (M3 Max). Good for real-time use.

**Bounding box details:**
- Coordinates are **normalized** (0-1), origin at **bottom-left**
- Convert to pixel coords: `Vision.VNImageRectForNormalizedRect(bbox, img_width, img_height)`
- Per-word bounding boxes in accurate mode; per-character only in fast mode
- Returns text + confidence score (0-1)

**Language support:** 20+ languages, auto-detection available.

**Key gotcha:** pyobjc issue #591 reports segfaults when calling VNRecognizeTextRequest repeatedly. Workaround: use `objc.autorelease_pool()` context manager.

**Dependencies:** `pyobjc-framework-Vision`, `pyobjc-framework-Quartz` (already in Nexus deps)

**References:**
- https://developer.apple.com/documentation/vision/vnrecognizetextrequest
- https://yasoob.me/posts/how-to-use-vision-framework-via-pyobjc/
- https://gist.github.com/RhetTbull/1c34fc07c95733642cffcd1ac587fc4c
- https://github.com/ronaldoussoren/pyobjc/issues/591

### 2.2 ocrmac Library (Python Wrapper)

**What it does:** Clean Python wrapper around Apple Vision framework OCR.

```python
from ocrmac import ocrmac

# Simple text extraction
results = ocrmac.OCR("/tmp/screenshot.png").recognize()
# Returns: [(text, confidence, (x, y, w, h)), ...]

# Or functional API
results = ocrmac.text_from_image("/tmp/screenshot.png")
```

**Three modes:**

| Mode | Speed (M3 Max) | Notes |
|------|----------------|-------|
| `accurate` | 207ms | Best accuracy, uses VNRecognizeTextRequest level 0 |
| `fast` | 131ms | Uses VNRecognizeTextRequest level 1 |
| `livetext` | 174ms | Uses VKCImageAnalyzer (macOS Sonoma+), stronger than Vision OCR |

**LiveText access:** Uses private API `VKCImageAnalyzer` via `objc.lookUpClass()`. Not officially documented but works reliably. Requires macOS Sonoma (14.0+).

**Bounding boxes:** All modes return normalized coordinates convertible to pixel positions.

**Dependencies:** `pip install ocrmac` (installs pyobjc-framework-Vision automatically)

**References:**
- https://github.com/straussmaximilian/ocrmac
- https://pypi.org/project/ocrmac/

### 2.3 Tesseract OCR

**What it does:** Open-source OCR engine, runs on CPU.

**macOS install:** `brew install tesseract`
**Python:** `pip install pytesseract`

```python
import pytesseract
from PIL import Image

text = pytesseract.image_to_string(Image.open("/tmp/screenshot.png"))
# With bounding boxes:
data = pytesseract.image_to_data(Image.open("/tmp/screenshot.png"), output_type=pytesseract.Output.DICT)
```

**Performance:**
- Speed: Slower than Apple Vision (~500ms-2s depending on image complexity)
- Accuracy: 80-85% general, heavily dependent on preprocessing
- Best with: clean printed text, 300 DPI, white background
- Struggles with: UI screenshots (mixed fonts, icons, colored backgrounds)

**Comparison to Apple Vision:**
| Aspect | Apple Vision | Tesseract |
|--------|-------------|-----------|
| Speed | 131-207ms | 500-2000ms |
| Accuracy (UI) | High | Medium (80-85%) |
| Bounding boxes | Yes (normalized) | Yes (pixel coords) |
| Language support | 20+ built-in | 100+ via traineddata |
| GPU acceleration | Yes (Neural Engine) | No (CPU only) |
| Dependencies | macOS only | Cross-platform |
| Preprocessing needed | Minimal | Significant |

**Verdict for Nexus:** Apple Vision is strictly better for our use case (macOS only, UI screenshots, speed matters). Tesseract adds no value and adds a dependency.

**References:**
- https://github.com/tesseract-ocr/tesseract
- https://pypi.org/project/pytesseract/

### 2.4 OCR Speed Summary for Nexus

For real-time UI automation on macOS, the target is under 200ms for OCR:

| Approach | Speed (M3 Max) | Accuracy | Dependencies |
|----------|---------------|----------|--------------|
| Vision Fast | **131ms** | Good | pyobjc (already have) |
| Vision Accurate | 207ms | Better | pyobjc (already have) |
| LiveText (VKCImageAnalyzer) | 174ms | Best | pyobjc + macOS 14+ |
| Tesseract | 500-2000ms | Medium | brew + pytesseract |

**Recommendation:** Use Apple Vision "fast" mode (131ms) for real-time element finding. Fall back to "accurate" mode when fast mode confidence is low. LiveText is a nice bonus for Sonoma+ users.

---

## 3. Screenshot + Coordinate Clicking Approaches

### 3.1 Anthropic Computer Use

**Architecture:** Pure screenshot-based. No accessibility API at all.

**The loop:**
1. Capture screenshot (full screen)
2. Send to Claude with the task description
3. Claude analyzes screenshot, identifies UI elements visually
4. Claude returns action: `click(x, y)`, `type("text")`, `press("key")`
5. Execute action via cliclick (macOS) or xdotool (Linux)
6. Capture new screenshot
7. Claude verifies success, continues or adjusts
8. Repeat until task complete

**Coordinate handling:** Claude counts pixels from screen edges to calculate exact cursor positions. Trained specifically on pixel counting for reliable coordinate estimation across resolutions.

**macOS implementation details:**
- Screenshots: `screencapture` CLI + ImageMagick for processing
- Input: `cliclick` (CLI tool for mouse/keyboard simulation)
- Coordinate mapping adjusts for screen resolution/DPI

**Zoom action:** Claude Opus 4.6/Sonnet 4.6 introduced `computer_20251124` tool with zoom capability for inspecting small screen regions in detail.

**Strengths:**
- Works with ANY application (no AX tree needed)
- Self-correcting (screenshot verification after each action)
- Handles arbitrary UI layouts

**Weaknesses:**
- Slow: each action requires full Claude API call (~1-5s latency)
- Expensive: every step uses vision tokens
- Pixel counting isn't perfectly accurate
- No structured understanding of UI hierarchy
- Blind to off-screen elements

**Nexus relevance:** This is the model for our "blind mode" fallback. But Nexus can be smarter -- we can combine local OCR (free, fast) with targeted Claude calls only when needed.

**References:**
- https://docs.anthropic.com/en/docs/build-with-claude/computer-use
- https://github.com/anthropics/claude-quickstarts/blob/main/computer-use-demo/computer_use_demo/loop.py
- https://github.com/newideas99/Anthropic-Computer-Use-MacOS
- https://github.com/PallavAg/claude-computer-use-macos

### 3.2 SikuliX (OpenCV Template Matching)

**Architecture:** Capture screenshot, find target image using OpenCV matchTemplate.

**How it works:**
1. User provides a reference image of the target element (e.g., a screenshot of the "Accept" button)
2. SikuliX captures a screenshot of the screen/region
3. OpenCV `matchTemplate()` slides the reference image over the screenshot pixel-by-pixel
4. Returns similarity scores for each position
5. Positions with score > 0.7 (default threshold) are considered matches
6. Click at the center of the matched region

**Performance:**
- matchTemplate with OpenCV: **<1ms** for full-screen search when using OpenCV's optimized implementation
- Full SikuliX pipeline (capture + match + click): ~100-500ms
- Much faster than vision model approaches

**Limitations:**
- Requires pre-captured reference images of every target element
- Brittle: breaks with theme changes, resolution changes, localization
- No semantic understanding ("click Save" doesn't work unless you have a "Save.png")
- Multi-scale matching needed if target can appear at different sizes

**Python implementation:**
```python
import cv2
import numpy as np
from PIL import Image

def find_element(screenshot_path, template_path, threshold=0.8):
    screenshot = cv2.imread(screenshot_path, cv2.IMREAD_GRAYSCALE)
    template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
    result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    locations = np.where(result >= threshold)
    # Returns (y_coords, x_coords)
    return list(zip(locations[1], locations[0]))  # (x, y) pairs
```

**Nexus relevance:** Not suitable as primary approach (requires reference images). But could be useful for verifying known UI patterns (e.g., detecting standard macOS dialog buttons by their visual appearance).

**References:**
- https://sikulix.github.io/docs/
- https://docs.opencv.org/4.x/d4/dc6/tutorial_py_template_matching.html

### 3.3 PyAutoGUI locateOnScreen

**What it does:** Built-in template matching in PyAutoGUI (already a Nexus dependency).

```python
import pyautogui

# Find image on screen
location = pyautogui.locateOnScreen('button.png', confidence=0.8)
# Returns Box(left, top, width, height) or None

# Click at center of found image
pyautogui.click(pyautogui.center(location))
```

**Performance:**
- Default (PIL-based): **1-2 seconds** per search on 1920x1080
- With OpenCV installed: **<1ms** per search (1000x faster!)
- Grayscale mode (`grayscale=True`): ~30% speedup
- Region limiting speeds proportionally

**Nexus relevance:** Already have pyautogui. Installing opencv-python would unlock fast template matching for free. Good for "is this dialog still showing?" type checks.

**References:**
- https://pyautogui.readthedocs.io/en/latest/screenshot.html
- https://github.com/asweigart/pyautogui/issues/168

---

## 4. Efficient Screenshot Transport

### 4.1 The Size Problem

Nexus's `see(screenshot=True)` was found to produce ~146KB base64 results, which exceeds comfortable MCP token limits. This section analyzes optimization strategies.

### 4.2 Format Comparison

**File sizes for a typical 2560x1440 UI screenshot:**

| Format | Quality | Typical Size | Base64 Size | Notes |
|--------|---------|-------------|-------------|-------|
| PNG | Lossless | 2-5MB | 2.7-6.7MB | Perfect quality, huge |
| JPEG q95 | Very high | 400-800KB | 530KB-1.1MB | Nearly lossless |
| JPEG q70 | Good | 150-300KB | 200-400KB | Good for visual analysis |
| JPEG q50 | Acceptable | 80-150KB | 107-200KB | OK for OCR |
| WebP q75 | Good | 100-200KB | 133-267KB | 25-34% smaller than JPEG |
| AVIF q60 | Good | 60-120KB | 80-160KB | 20-30% smaller than WebP |

**Base64 overhead:** +33% over binary size. A 100KB JPEG becomes ~133KB in base64.

**Current Nexus approach:** JPEG q70 at max 1280px width. This is a good default.

### 4.3 Resolution Requirements

**For OCR accuracy:**
- Minimum: 150 DPI equivalent (~18px vertical per uppercase character)
- Recommended: 300 DPI equivalent
- For UI text at 12-14pt, 1280px wide screenshot of a 2560px screen (50% scale) still gives ~24px character height -- adequate for OCR

**For visual element identification:**
- Human/AI identification: 720-1024px width is usually sufficient
- Claude vision: works well with 1024-1568px images (per Anthropic docs)
- Retina screens: capturing at 1x logical resolution (not 2x physical) saves 75% pixels

**For template matching:**
- Needs same resolution as reference images
- Region-based capture avoids needing to process full-screen images

### 4.4 Region-Based Capture

Instead of capturing the full screen, capture only the area of interest:

```python
# Using CGWindowListCreateImage with region
from Quartz import CGRectMake, CGWindowListCreateImage

rect = CGRectMake(x, y, width, height)
cg_image = CGWindowListCreateImage(rect, ...)

# Using screencapture CLI
import subprocess
subprocess.run(["screencapture", "-x", "-R", f"{x},{y},{w},{h}", "/tmp/region.png"])
```

**Size savings:** A 400x300 region capture is ~1/30th the pixels of a full 2560x1440 screen.

**Use cases:**
- Capture area around a click point to verify action succeeded
- Capture a known dialog location to OCR its text
- Capture a specific window only

### 4.5 Optimal Transport Strategy for Nexus

| Scenario | Resolution | Format | Expected Size (b64) |
|----------|-----------|--------|-------------------|
| Full screen for AI | 1280px wide | JPEG q60 | 100-200KB |
| Region verification | Native | JPEG q70 | 10-30KB |
| Window capture | 1024px wide | JPEG q65 | 50-100KB |
| OCR input | Native (or 50% Retina) | PNG | N/A (local only) |

**Key insight:** OCR should happen locally (no transport needed). Only send images to the AI when visual understanding is required. This eliminates 90% of screenshot transport.

**References:**
- https://platform.claude.com/docs/en/build-with-claude/vision
- https://bulkimagepro.com/articles/webp-vs-jpeg-vs-png-compression/

---

## 5. Vision Models for UI Understanding

### 5.1 Claude Vision (Current Capability)

**Strengths:**
- Excellent semantic understanding ("find the Accept button")
- Can read text, understand layout, identify UI patterns
- Available in Claude Code via MCP (the AI is already running)
- Pixel counting for coordinates (trained for Computer Use)

**Weaknesses:**
- Bounding box coordinates are unreliable across runs
- Not trained for precise pixel-level localization
- Each call costs API tokens + 1-5s latency
- Cannot replace OCR for structured data extraction

**Practical pattern:** Don't ask Claude "what are the coordinates of X?" Instead, use local OCR to find text, template matching for known patterns, and only fall back to Claude vision for ambiguous cases.

### 5.2 Google Gemini Vision

**Unique capability:** Natively trained to output bounding box coordinates. Returns normalized coordinates (0-1000 scale).

**Better than Claude at:** Precise element localization
**Worse than Claude at:** Complex multi-step reasoning about what to do

**Not directly usable in Nexus** (would need a separate API key and provider), but worth noting as the state of the art for visual grounding from a foundation model.

### 5.3 SeeClick (GUI Grounding Model)

**What it does:** Maps (screenshot, instruction) pairs to actionable click locations. Built on Qwen-VL.

**Performance:** Best on ScreenSpot benchmark across mobile, desktop, and web GUIs with fewer parameters than CogAgent.

**Key insight:** Created ScreenSpot, the first realistic GUI grounding benchmark for mobile/desktop/web.

**Feasibility for Nexus:** Would require running a local model (~7B parameters). Too heavy for real-time automation unless pre-loaded.

**References:**
- https://github.com/njucckevin/SeeClick
- https://arxiv.org/abs/2401.10935

### 5.4 CogAgent

**What it does:** 18B-parameter VLM for GUI understanding. Supports 1120x1120 input resolution.

**Performance:** Outperforms LLM-based methods on PC and Android navigation tasks.

**Feasibility for Nexus:** Way too large for local real-time use. Server deployment possible but adds latency.

**References:**
- https://www.semanticscholar.org/paper/CogAgent-Hong-Wang/e50583008fe4ec049e42fdc01727ce98f6d86a35

### 5.5 OmniParser V2 (Microsoft, February 2025)

**What it does:** Parses UI screenshots into structured element lists with interactable regions and icon descriptions. Two fine-tuned models: a detection model (YOLOv8) and a caption model.

**Performance:**
- Latency: **0.6s/frame on A100, 0.8s on RTX 4090**
- Accuracy: 39.6% on ScreenSpot Pro (state of the art for parsing)
- 60% latency improvement over V1

**Architecture:** Detection model identifies interactable elements (buttons, fields, links, icons). Caption model describes each element's function.

**Feasibility for Nexus:**
- Requires GPU (CUDA recommended)
- Could run locally on Apple Silicon via MPS backend
- ~0.8-1.5s per frame on consumer hardware (estimated)
- Open source, weights available on HuggingFace

**Most promising local model option** for screenshot parsing without cloud API calls.

**References:**
- https://github.com/microsoft/OmniParser
- https://huggingface.co/microsoft/OmniParser-v2.0
- https://microsoft.github.io/OmniParser/

### 5.6 UI-TARS (ByteDance, January 2025)

**What it does:** Native GUI agent model. Takes screenshot input, outputs keyboard/mouse operations.

**Performance:** State of the art on 10+ GUI benchmarks. OSWorld: 24.6 score (outperforms Claude on this benchmark).

**Feasibility for Nexus:** Research model, not easily deployable. Interesting as a benchmark reference.

**References:**
- https://arxiv.org/abs/2501.12326

### 5.7 Screen2AX (MacPaw, 2025)

**What it does:** Reconstructs macOS accessibility trees from screenshots using YOLOv11 + BLIP.

**Architecture:**
1. YOLOv11 detects UI elements (buttons, text fields, checkboxes, etc.)
2. BLIP generates descriptions for each detected element
3. Second YOLOv11 model organizes elements into hierarchical structure

**Performance:**
- F1 score of 79% for accessibility hierarchy reconstruction
- Improves grounding accuracy by **2.2x** over native accessibility metadata
- Outperforms OmniParser V2 on ScreenSpot benchmark for textual representations

**Available models on HuggingFace:**
- `MacPaw/yolov11l-ui-elements-detection` - UI element detection
- `MacPaw/yolov11l-ui-groups-detection` - Group/hierarchy detection

**Companion tool: macapptree**
```python
# pip install macapptree
import macapptree
# Extracts AX tree + can capture labeled screenshots with bounding boxes
```

**Feasibility for Nexus:** This is the most relevant research for our exact problem. Designed specifically for macOS, generates AX-tree-like structured output from screenshots. YOLOv11 is lightweight enough for real-time use.

**References:**
- https://github.com/MacPaw/Screen2AX
- https://github.com/MacPaw/macapptree
- https://huggingface.co/MacPaw/yolov11l-ui-elements-detection
- https://arxiv.org/html/2507.16704v1

### 5.8 Vision Model Summary

| Model | Type | Speed | Accuracy | Local? | Best For |
|-------|------|-------|----------|--------|----------|
| Claude Vision | Cloud LLM | 1-5s | High (semantic) | No | Understanding "what to click" |
| Gemini Vision | Cloud LLM | 1-3s | High (grounding) | No | Precise coordinates |
| OmniParser V2 | Local detection | 0.6-1.5s | 39.6% ScreenSpot Pro | Yes (GPU) | Element detection |
| Screen2AX | Local detection | ~0.5-1s (est) | 79% F1 (hierarchy) | Yes | AX tree reconstruction |
| SeeClick | Local VLM | ~1-2s (est) | Strong on ScreenSpot | Yes (7B) | Click target finding |
| Apple Vision OCR | Local framework | 131-207ms | >95% (text) | Yes | **Text extraction** |

---

## 6. Hybrid Approaches

### 6.1 AX Tree + Screenshot Fallback (Recommended for Nexus)

**Strategy:**
```
1. Try AX tree (current Nexus behavior) -- ~50ms
   - If tree has elements --> use them (fast, structured, reliable)
2. If tree is empty/minimal (<5 elements):
   a. Capture screenshot of the target window -- ~20-100ms
   b. Run Apple Vision OCR on the screenshot -- ~131ms (fast mode)
   c. Build a "virtual AX tree" from OCR results:
      - Each text region becomes a clickable element
      - Bounding box provides click coordinates
      - Confidence score indicates reliability
   d. Return combined tree to the AI agent
3. For "click X" when X is only in OCR results:
   - Use bounding box center as click coordinate
   - After clicking, re-screenshot and verify change
```

**Total latency for fallback path:** ~250-400ms (screenshot + OCR + processing)

### 6.2 OCR to Supplement Partial AX Trees

Some apps expose partial AX trees (e.g., Docker Desktop with only 4 window-frame elements, but visible UI has dozens of buttons/text).

**Strategy:**
```
1. Get AX tree (partial)
2. Capture screenshot
3. Run OCR
4. For each OCR text region:
   - If it overlaps with an AX element's bounds --> skip (AX element is better)
   - If it's in an area with no AX elements --> add as a "visual element"
5. Merge into unified element list
```

### 6.3 Screenshot Diff for Change Detection (AX-tree-less)

When AX tree is empty, we can still detect UI changes using screenshot comparison.

**Strategy:**
```python
from PIL import Image
import numpy as np

def screenshot_diff(before, after, threshold=30):
    """Detect changed regions between two screenshots.

    Returns list of (x, y, w, h) bounding boxes for changed areas.
    """
    arr1 = np.array(before.convert("L"))  # Grayscale
    arr2 = np.array(after.convert("L"))
    diff = np.abs(arr1.astype(int) - arr2.astype(int))
    mask = diff > threshold

    # Find bounding boxes of changed regions
    # (use connected components or contour detection)
    from scipy.ndimage import label
    labeled, num_features = label(mask)
    regions = []
    for i in range(1, num_features + 1):
        ys, xs = np.where(labeled == i)
        regions.append((xs.min(), ys.min(), xs.max() - xs.min(), ys.max() - ys.min()))
    return regions
```

**Alternative: pixelmatch library:**
```python
# pip install pixelmatch
from pixelmatch.contrib.PIL import pixelmatch

diff_count = pixelmatch(img1, img2, diff_output, alpha=0.1, threshold=0.1)
```

**Use case in Nexus:** After a blind click, capture before/after screenshots and check if anything changed in the expected region. Provides feedback even without AX tree.

### 6.4 CoDriver MCP's Approach

CoDriver-MCP implements the full hybrid:
1. `desktop_read_ui` -- accessibility tree with ref IDs
2. `desktop_screenshot` -- PNG/JPEG capture
3. `desktop_ocr` -- text recognition
4. `desktop_find` -- element search

Uses JXA/osascript for macOS accessibility (lighter than pyobjc but less powerful).

**References:**
- https://github.com/ViktorTrn/codriver-mcp

---

## 7. Relevant GitHub Repos

### 7.1 macOS Automation + Screenshot + OCR Projects

| Repository | Stars | Description | Key Technique |
|-----------|-------|-------------|--------------|
| [steipete/Peekaboo](https://github.com/steipete/Peekaboo) | High | macOS CLI & MCP for AI screenshots + VQA | ScreenCaptureKit (Swift) + multi-AI providers |
| [MacPaw/Screen2AX](https://github.com/MacPaw/Screen2AX) | New | Reconstruct AX trees from screenshots | YOLOv11 + BLIP |
| [MacPaw/macapptree](https://github.com/MacPaw/macapptree) | -- | macOS AX tree extraction + labeled screenshots | Python, AX API |
| [straussmaximilian/ocrmac](https://github.com/straussmaximilian/ocrmac) | 200+ | Python wrapper for Apple Vision OCR | VNRecognizeTextRequest, VKCImageAnalyzer |
| [kxrm/vision](https://github.com/kxrm/vision) | -- | Vision-based macOS automation tools | Screenshots, OCR, mouse/keyboard |
| [PeterHdd/macos-control-mcp](https://github.com/PeterHdd/macos-control-mcp) | -- | MCP for screenshots, OCR, click, type | Apple Vision + CGEvents |
| [ViktorTrn/codriver-mcp](https://github.com/ViktorTrn/codriver-mcp) | -- | Hybrid AX tree + screenshot + OCR automation | Multi-platform, tesseract.js |
| [mb-dev/macos-ui-automation-mcp](https://github.com/mb-dev/macos-ui-automation-mcp) | -- | Simple MCP for native macOS app control | Accessibility-based |
| [TIMBOTGPT/screen-vision-mcp](https://github.com/TIMBOTGPT/screen-vision-mcp) | -- | MCP for capture, OCR, visual understanding | macOS focused |
| [ohqay/mac-commander](https://github.com/ohqay/mac-commander) | -- | MCP for macOS app automation | Screenshots + OCR + automation |
| [microsoft/OmniParser](https://github.com/microsoft/OmniParser) | 10K+ | Screen parsing for vision GUI agents | YOLOv8 + icon captioning |
| [njucckevin/SeeClick](https://github.com/njucckevin/SeeClick) | 300+ | Visual GUI agent grounding model | Qwen-VL fine-tuned |
| [dynobo/normcap](https://github.com/dynobo/normcap) | 3K+ | OCR screen capture tool | Cross-platform, Tesseract |
| [newideas99/Anthropic-Computer-Use-MacOS](https://github.com/newideas99/Anthropic-Computer-Use-MacOS) | 500+ | Computer Use on native macOS | screencapture + cliclick |
| [smokris/GetWindowID](https://github.com/smokris/GetWindowID) | 100+ | Get CGWindowID for screencapture -l | Utility, brew installable |
| [sassman/son-of-grab](https://github.com/sassman/son-of-grab) | -- | CG Window API demo, updated for macOS 11 | CGWindowListCreateImage |
| [Doriandarko/Claude-Vision-Object-Detection](https://github.com/Doriandarko/Claude-Vision-Object-Detection) | -- | Object detection with Claude vision | Bounding box visualization |
| [RhetTbull/vision-ocr-gist](https://gist.github.com/RhetTbull/1c34fc07c95733642cffcd1ac587fc4c) | -- | Apple Vision OCR from Python | VNRecognizeTextRequest example |

### 7.2 Most Relevant for Nexus

1. **ocrmac** -- could directly use or vendor the key functions for Apple Vision OCR
2. **Screen2AX** -- their YOLOv11 models for UI element detection are exactly what we'd need for full visual parsing
3. **Peekaboo** -- architectural reference for how to build a production MCP with screenshot + AI vision
4. **macapptree** -- lightweight Python AX tree extraction, potential alternative to our pyobjc approach

---

## 8. Recommendations for Nexus

### 8.1 Phase 1: Quick Win (Days)

**Add local OCR fallback when AX tree is empty.**

Implementation plan:
1. Add `ocr_screenshot(image)` function to `nexus/sense/` using Apple Vision via pyobjc (no new deps)
2. In `nexus/sense/fusion.py`, after `describe_app()`:
   - If element count < 5, capture window screenshot and run OCR
   - Build virtual elements from OCR results: `{role: "text", label: text, bounds: bbox, source: "ocr"}`
   - Merge into element list
3. In `nexus/act/resolve.py`, when element-not-found:
   - If any OCR elements exist, find nearest text match
   - Click at bounding box center coordinates

**Code sketch for OCR module:**
```python
# nexus/sense/ocr.py
"""On-device OCR via Apple Vision framework."""

import objc
import Vision
from Quartz import CIImage
from Foundation import NSDictionary


def ocr_image(pil_image, mode="fast"):
    """Run OCR on a PIL Image, return list of (text, confidence, x, y, w, h).

    Coordinates are in pixel space (top-left origin).
    mode: "fast" (~131ms) or "accurate" (~207ms)
    """
    # Convert PIL to CIImage via PNG buffer
    import io
    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    data = Foundation.NSData.dataWithBytes_length_(buf.getvalue(), len(buf.getvalue()))
    ci_image = CIImage.imageWithData_(data)

    with objc.autorelease_pool():
        request = Vision.VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLevel_(1 if mode == "fast" else 0)

        handler = Vision.VNImageRequestHandler.alloc().initWithCIImage_options_(
            ci_image, NSDictionary.dictionary()
        )
        success, error = handler.performRequests_error_([request], None)

        if not success:
            return []

        results = []
        img_w, img_h = pil_image.size
        for obs in request.results():
            candidate = obs.topCandidates_(1)[0]
            text = candidate.string()
            confidence = candidate.confidence()

            # Convert normalized bbox (bottom-left origin) to pixel coords (top-left origin)
            bbox = obs.boundingBox()
            x = int(bbox.origin.x * img_w)
            y = int((1 - bbox.origin.y - bbox.size.height) * img_h)
            w = int(bbox.size.width * img_w)
            h = int(bbox.size.height * img_h)

            results.append((text, confidence, x, y, w, h))

        return results
```

**Expected impact:** Enables Nexus to "see" system dialogs, Gatekeeper prompts, and empty-tree Electron apps via text recognition. No new dependencies.

### 8.2 Phase 2: Window-Targeted Capture (Days)

**Add window-specific screenshot capture.**

1. Add `capture_window(pid)` to `nexus/sense/screen.py`:
   - Use `CGWindowListCopyWindowInfo` to find window IDs for the PID
   - Use `screencapture -x -l <windowID> /tmp/nexus_capture.png` for simplicity
   - Or use `CGWindowListCreateImage` with `kCGWindowListOptionIncludingWindow`
2. Use this for targeted OCR (much faster than full-screen OCR on a smaller image)

### 8.3 Phase 3: Screenshot Diff Verification (Week)

**Add visual change detection for blind actions.**

1. Before any `do()` action: capture region screenshot around target area
2. After action: capture same region
3. Compare with pixelmatch or numpy diff
4. Report "screen changed: yes/no, changed regions: [...]" in action result
5. If no change detected after click: report as potential miss

### 8.4 Phase 4: Smart OCR Element Finding (Weeks)

**Use OCR bounding boxes for element matching in resolve.py.**

When `do("click Accept")` fails to find "Accept" in AX tree:
1. Run OCR on the active window
2. Find "Accept" in OCR results (fuzzy match)
3. Calculate click coordinates from bounding box center
4. Adjust for window position on screen
5. Click at absolute screen coordinates via pyautogui
6. Verify with post-click screenshot diff

### 8.5 Phase 5: ScreenCaptureKit Migration (Month)

**Migrate from deprecated CGWindowListCreateImage to ScreenCaptureKit.**

This is non-urgent (CGWindowListCreateImage still works on macOS 14) but necessary for macOS 15+ compatibility. The main challenge is ScreenCaptureKit's async callback API vs Nexus's synchronous architecture.

Options:
- Use `screencapture` CLI as the bridge (simplest, already works)
- Write a small Swift helper that uses ScreenCaptureKit and outputs to stdout/file
- Use pyobjc with CFRunLoop synchronization (complex but pure Python)

### 8.6 Future: Local UI Element Detection Model (Quarter)

**Integrate Screen2AX or OmniParser for full visual AX tree reconstruction.**

This would give Nexus "eyes" comparable to AX API access, purely from screenshots. Consider:
- Screen2AX's YOLOv11 models are lightweight (~50MB)
- Could run on Apple Neural Engine via CoreML conversion
- Would provide structured element detection even for apps with zero AX support
- Not needed immediately -- OCR fallback covers 80% of blind cases

### 8.7 Decision Matrix

| Approach | Effort | Impact | Latency | Dependencies |
|----------|--------|--------|---------|-------------|
| Phase 1: OCR fallback | 2 days | **High** | +131-207ms | None (pyobjc) |
| Phase 2: Window capture | 1 day | Medium | +50-200ms | None |
| Phase 3: Screenshot diff | 2-3 days | Medium | +50-100ms | numpy (optional) |
| Phase 4: OCR click | 3-5 days | **High** | +200-400ms | None |
| Phase 5: ScreenCaptureKit | 1 week | Low (future-proof) | Faster | pyobjc-framework-ScreenCaptureKit |
| Phase 6: YOLO detection | 2-4 weeks | **Very high** | +500-1500ms | ultralytics, torch |

---

## Appendix A: System Dialog Detection

CoreServicesUIAgent and SecurityAgent run system dialogs (Gatekeeper verification, network permissions, password prompts) that are invisible to the AX API.

**Detection strategy:**
```python
from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID

def find_system_dialogs():
    """Find CoreServicesUIAgent/SecurityAgent windows."""
    windows = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
    dialogs = []
    for w in windows:
        owner = w.get('kCGWindowOwnerName', '')
        if owner in ('CoreServicesUIAgent', 'SecurityAgent', 'UserNotificationCenter'):
            dialogs.append({
                'owner': owner,
                'name': w.get('kCGWindowName', ''),
                'id': w['kCGWindowNumber'],
                'bounds': w.get('kCGWindowBounds', {}),
                'pid': w.get('kCGWindowOwnerPID', 0),
            })
    return dialogs
```

Then capture + OCR these windows to understand their content and act on them.

## Appendix B: Quick Reference -- ocrmac Python Code

```python
# Minimal working OCR using Apple Vision (no external deps beyond pyobjc)
import Vision
from Quartz import CIImage
from Foundation import NSDictionary, NSData
import objc, io

def quick_ocr(pil_image):
    """Returns list of (text, confidence) tuples."""
    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    raw = buf.getvalue()

    ns_data = NSData.dataWithBytes_length_(raw, len(raw))
    ci_image = CIImage.imageWithData_(ns_data)

    with objc.autorelease_pool():
        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(1)  # fast

        handler = Vision.VNImageRequestHandler.alloc().initWithCIImage_options_(
            ci_image, NSDictionary.dictionary()
        )
        success, error = handler.performRequests_error_([req], None)

        if not success:
            return []

        return [
            (obs.topCandidates_(1)[0].string(), obs.topCandidates_(1)[0].confidence())
            for obs in req.results()
        ]
```

## Appendix C: Full Window Capture by PID

```python
from Quartz import (
    CGWindowListCopyWindowInfo,
    kCGWindowListOptionOnScreenOnly,
    kCGNullWindowID,
)
import subprocess, os

def capture_window_by_pid(pid, output_path="/tmp/nexus_window.png"):
    """Capture the main window of a process by its PID."""
    windows = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)

    # Find the largest on-screen window for this PID
    best = None
    best_area = 0
    for w in windows:
        if w.get('kCGWindowOwnerPID') == pid:
            bounds = w.get('kCGWindowBounds', {})
            area = bounds.get('Width', 0) * bounds.get('Height', 0)
            if area > best_area:
                best = w
                best_area = area

    if not best:
        return None

    window_id = best['kCGWindowNumber']
    subprocess.run(
        ["screencapture", "-x", "-o", "-l", str(window_id), output_path],
        check=True,
        timeout=5,
    )

    from PIL import Image
    return Image.open(output_path)
```
