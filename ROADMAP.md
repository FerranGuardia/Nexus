# Nexus Roadmap

Private research directions and architectural compass.

---

## What Nexus Is

A toolkit that gives AI agents (Claude Code, Cursor, any MCP client) the ability to see and control a computer. Born from the frustration that LLMs can reason about anything but can't reach the last-mile automation — connecting accounts, clicking through setup wizards, handling native UI that has no API.

Nexus closes the gap between "I can write a script for that" and "I have to do it manually."

## Three Pillars

| Pillar | Role | Current deps (Windows) |
|--------|------|----------------------|
| **Oculus** (the Eye) | Observation — UIA tree, CDP accessibility, OCR, vision | pywinauto, playwright, tesseract |
| **Digitus** (the Hand) | Action — click, type, navigate, COM automation | pyautogui, pywin32 |
| **Cortex** (the Brain) | Processing — compact formatting, pruning, summarization, memory | pure Python (no OS deps) |

**Nexus** itself is the linker: MCP server, CLI, batch execution, shared infrastructure (CDP connections, caching).

### Boundaries

Every piece of code has one home:
- **See something?** → Oculus
- **Do something?** → Digitus
- **Process/compress something?** → Cortex
- **Connect/orchestrate?** → Nexus core

Connections between pillars are expected. The rule is clarity of ownership, not isolation.

---

## Research Directions

### 1. Information Channel Efficiency

The biggest opportunity. Right now the desktop-to-LLM pipe is clunky:
- Screenshots are expensive (multimodal tokens)
- UIA dumps are noisy (thousands of elements, most irrelevant)
- The LLM re-tokenizes text that was already structured

**Ideas to explore:**
- **Pre-tokenization**: transform UI state into a representation optimized for the model's tokenizer before it leaves the local machine
- **Continuous awareness**: if observation is cheap enough, the agent can maintain persistent desktop state instead of point-in-time snapshots
- **Learned compression**: can Cortex learn which elements matter for a given task and drop the rest?

This is where Cortex becomes the star of the project.

### 2. OS Abstraction

Nexus is Windows-only today (UIA, COM, pywin32). macOS has reportedly better accessibility APIs.

**Plan:**
- Explore macOS accessibility (AXUIElement) — is the tree richer? More reliable?
- If Mac works better, it may become the primary platform
- Goal: same tool surface regardless of OS. The agent doesn't care if it's Windows or Mac — it calls `describe()` and gets a UI tree

**Split consequence:** Oculus and Digitus get OS-specific backends. Cortex stays universal.

### 3. Lighter Vision

OmniParser works but is too heavy:
- Requires CUDA + PyTorch (~1.1GB models)
- ~26s per detection call
- Separate sidecar process on port 8500

**Alternatives to explore:**
- Lightweight local models (YOLO-based UI detection, smaller than OmniParser)
- Cloud vision APIs (fast, no local GPU, but adds latency and cost)
- Hybrid: OCR + heuristic layout analysis (no ML, just geometry)
- Pre-tokenized visual descriptions (ties back to research direction #1)

### 4. Permission Flow

Daily pain: Nexus positions on a window, takes a screenshot, but the user has to switch to VS Code to approve the tool call. Focus changes, screenshot goes stale, needs to re-acquire.

**Ideas:**
- Batch operations / action chains that require one approval for a sequence
- Trust levels per tool category (observation = auto-approve, actions = ask)
- This is partially an MCP client problem (Claude Code's permission model), not just Nexus

---

## Architecture Decisions (Open)

### Monorepo vs Multi-repo
- **Current**: monorepo, subpackages under `nexus/`
- **Direction**: split into standalone packages (oculus, cortex, digitus) + nexus as linker
- **Timing**: now — codebase is small, cost of splitting is low
- Shared infra (cdp.py, cache.py) stays in nexus core

### Open vs Closed
- **Undecided**. Options on the table:
  - MIT open source from day one (build reputation, get community ideas)
  - Private until product-ready (launch big, monetize directly)
  - Open core (basic tools open, Cortex intelligence proprietary)
- **Current stance**: don't commit yet. Explore Mac, test the architecture split, then decide

### Mac Viability
- Need to research macOS accessibility APIs before committing
- The split into OS-specific backends should happen before Mac exploration so the architecture is ready

---

## Immediate Next Steps

1. **Split the pillars** — separate oculus, digitus, cortex into clean standalone packages within the repo (or subrepos). Nexus core keeps MCP server, CLI, CDP, caching
2. **Push to GitHub** (private) — need remote to work from Mac
3. **Mac research** — explore AXUIElement, AppleScript, macOS accessibility. Can Oculus work there?
4. **Cortex experiments** — prototype pre-tokenization. Take a UIA tree dump, compress it, measure token count vs information preserved
5. **Lighter vision** — benchmark alternatives to OmniParser. What's the minimum viable vision?

---

## What This Is NOT

- Not a product (yet, maybe ever)
- Not a framework others build on (but contributions welcome)
- Not a Playwright replacement — it's what you use when Playwright can't reach
- Not locked to Windows — that's just where it started
