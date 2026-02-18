# NX-007: Set-of-Mark Annotation

**Branch:** `task/NX-007-set-of-mark`
**Status:** PENDING
**Depends on:** None (enhanced by NX-006 OCR, NX-010 OmniParser)
**Tracking:** `.claude/tasks/INDEX.md`
**Started:** —
**Finished:** —

---

> **In plain English:** When Claude takes a screenshot, it sees pixels but can't precisely reference
> elements. Overlay numbered labels on each interactive element so Claude can say "click element 7"
> and Nexus looks up the exact coordinates.

---

## What

- Add `screenshot --mark` flag that annotates the screenshot with numbered labels
- For each detected element (from UIA tree or web AXTree), draw a small numbered badge at its position
- Return both: the annotated image AND a lookup table `{ "1": {name, role, x, y, w, h}, "2": ... }`
- Claude says "click 7" → Nexus resolves to center coordinates → clicks
- Add `click-mark N` command as shorthand for clicking a marked element
- Use Pillow for image annotation (already installed)
- Badge style: small red/orange circle with white number, positioned at element top-left

## Why

Set-of-Mark eliminates coordinate hallucination entirely. Instead of Claude guessing pixel coordinates from a screenshot, it references numbered elements. SeeAct (ICML 2024) and Browser-Use hit 89.1% accuracy with this pattern. Anthropic's own computer-use demos use it.

## Where

- **Read:** `nexus/digitus/input.py` (screenshot), `nexus/uia.py` (element collection), `nexus/oculus/web.py` (web-ax)
- **Write:**
  - `nexus/mark.py` (new) — annotation logic: draw badges on image, build lookup table
  - `nexus/digitus/input.py` — add `--mark` flag to screenshot command
  - `nexus/run.py` — add `click-mark` command, wire `--mark` flag
  - `nexus/tests/test_mark.py` (new) — unit tests for annotation

## Validation

- [ ] `screenshot --mark` returns an annotated image with numbered badges
- [ ] Lookup table maps each number to element name, role, and bounding box
- [ ] `click-mark 5` clicks the center of element 5 from the last marked screenshot
- [ ] Badges are visually clear: readable numbers, don't obscure the element
- [ ] Works with UIA elements (native apps) and web AXTree nodes
- [ ] Handles overlapping elements gracefully (badges don't stack unreadably)
- [ ] Unit tests for badge placement logic
- [ ] E2E test: mark screenshot → click-mark → verify action happened

---

## Not in scope

- OmniParser element detection as a source (that's NX-010, but Set-of-Mark can use its output when available)
- Vision model for understanding the screenshot (Claude does that)
