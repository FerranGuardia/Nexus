# NX-006: Windows OCR (`ocr-region`)

**Branch:** `task/NX-006-windows-ocr`
**Status:** PENDING
**Depends on:** None
**Tracking:** `.claude/tasks/INDEX.md`
**Started:** —
**Finished:** —

---

> **In plain English:** When apps have no accessibility tree (games, canvas, PDFs, custom UIs),
> Nexus is blind. Add OCR that reads text from any screen region using Windows' built-in engine.

---

## What

- Add `ocr-region X Y W H` command: screenshot a region → OCR → return text + word bounding boxes
- Use `winrt-Windows.Media.Ocr` (native Windows OCR, no GPU, no external service)
- Fallback: `screen-ocr` library if WinRT is problematic
- Return: `{ "text": "full text", "words": [{"text": "word", "bounds": {x,y,w,h}}] }`
- Add `ocr-screen` variant that OCRs the entire active window
- Language detection: default to system language, `--lang` flag for override

## Why

OCR is the last-resort perception layer. Charts, canvas elements, PDF viewers, game UIs, custom-rendered controls — none have accessibility trees. OCR bridges the gap. Required by NX-011 (measure-image) and NX-007 (Set-of-Mark).

## Where

- **Read:** `nexus/digitus/input.py` (screenshot logic)
- **Write:**
  - `nexus/oculus/ocr.py` (new) — OCR functions: `ocr_region()`, `ocr_screen()`
  - `nexus/run.py` — add `ocr-region` and `ocr-screen` subcommands
  - `nexus/tests/test_ocr.py` (new) — unit tests with test images

## Validation

- [ ] `ocr-region 0 0 500 200` returns recognized text from that screen area
- [ ] Word bounding boxes are returned alongside text
- [ ] `ocr-screen` OCRs the full active window
- [ ] Works on: Notepad text, Chrome rendered content, a PNG image in Photos
- [ ] `--lang en` flag works for language override
- [ ] Returns empty result gracefully when no text is found (not an error)
- [ ] Unit tests with sample images
- [ ] E2E test: OCR a known text region

---

## Not in scope

- OmniParser / ML-based element detection (that's NX-010)
- Set-of-Mark annotation (that's NX-007)
