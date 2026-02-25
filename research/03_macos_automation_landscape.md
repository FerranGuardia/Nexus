# macOS Automation Landscape Research

**Date:** 2026-02-24
**Purpose:** Comprehensive survey of macOS automation tools, frameworks, and AI agent projects relevant to Nexus.

---

## Table of Contents

1. [Power-User Automation Tools](#1-power-user-automation-tools)
2. [Command-Line & Low-Level Tools](#2-command-line--low-level-tools)
3. [Commercial / Closed-Source Tools](#3-commercial--closed-source-tools)
4. [Apple's Own Automation Stack](#4-apples-own-automation-stack)
5. [Python Libraries for macOS Accessibility](#5-python-libraries-for-macos-accessibility)
6. [Anthropic Computer Use & Official Ports](#6-anthropic-computer-use--official-ports)
7. [MCP Servers for macOS](#7-mcp-servers-for-macos)
8. [AI Agents That Control macOS (2024-2026)](#8-ai-agents-that-control-macos-2024-2026)
9. [Research & Academic Projects](#9-research--academic-projects)
10. [Curated Lists & Meta-Resources](#10-curated-lists--meta-resources)
11. [Key Takeaways for Nexus](#11-key-takeaways-for-nexus)

---

## 1. Power-User Automation Tools

### Hammerspoon

- **URL:** https://github.com/Hammerspoon/hammerspoon
- **Homepage:** https://www.hammerspoon.org/
- **Stars:** ~14.5k
- **Language:** Objective-C + Lua scripting
- **Latest:** v1.1.0 (Dec 2024)
- **License:** MIT

**What it does:** Bridges dozens of macOS system APIs into a Lua scripting engine. Users write `~/.hammerspoon/init.lua` to automate anything.

**Accessibility APIs exposed:**
- `hs.axuielement` -- full AXUIElement wrapper. Can read/write any accessibility attribute, perform actions, walk the tree, and observe changes.
- `hs.axuielement.observer` -- AXObserver wrapper for monitoring accessibility notifications (equivalent to Nexus's `observe.py`).
- `hs.axuielement.axtextmarker` -- AXTextMarker/AXTextMarkerRange support for complex text APIs (undocumented Apple APIs).
- `hs.application` -- application lifecycle (launch, kill, focus, hide, list windows).
- `hs.window` -- window management (move, resize, minimize, fullscreen, frame, role filtering).
- `hs.window.filter` -- reactive window filters (subscribe to window events, filter by app/role/etc.).
- `hs.spaces` -- Mission Control spaces manipulation (uses accessibility actions through Dock.app).

**How it handles system dialogs:**
- Can filter windows by `subrole` ("AXStandardWindow", "AXDialog", etc.).
- Cannot directly access CoreServicesUIAgent dialogs (Gatekeeper, password prompts) -- same limitation as Nexus.
- Can detect window creation events and respond to dialogs programmatically.

**What Hammerspoon can do that pyobjc can't:**
- Nothing fundamental -- both access the same underlying ObjC APIs. But Hammerspoon wraps them more ergonomically for interactive use.
- Hammerspoon has `hs.eventtap` for global CGEvent interception (key presses, mouse events) with a simpler API than raw CGEventTap via pyobjc.
- Has `hs.screen.watcher`, `hs.caffeinate.watcher`, `hs.wifi.watcher` for system event monitoring out of the box.
- Plugin ecosystem ("Spoons") for reusable modules.

**Relevance to Nexus:**
- The `hs.axuielement` module is the gold standard for Lua AX access. Its observer implementation and AXTextMarker support show what's possible.
- Hammerspoon's approach of wrapping C APIs in a scripting language is exactly what Nexus does with Python/pyobjc.
- Could potentially use Hammerspoon as a subprocess for operations that are hard via pyobjc (e.g., `hs.spaces` manipulation).

---

### yabai

- **URL:** https://github.com/koekeishiya/yabai
- **Stars:** ~25.2k
- **Language:** C
- **License:** MIT

**What it does:** Tiling window manager for macOS. Automatically arranges windows using binary space partitioning.

**How it interacts with accessibility:**
- Requires Accessibility permission to observe and move windows.
- Uses standard AXUIElement APIs for basic window queries and manipulation.
- For advanced features (spaces, window opacity, window layers), it **injects a scripting addition into Dock.app** via Mach APIs.

**Private APIs used:**
- **CGSConnection** -- the private Core Graphics Server connection that Dock.app holds to the WindowServer. Yabai injects code into Dock.app to get this connection.
- Requires **partial SIP (System Integrity Protection) disabling** to inject into Dock.app.
- Uses `task_for_pid()` and Mach injection APIs that require root privileges.
- After injection, can call private CGS functions to: move windows between spaces, change window levels/opacity, animate, and query the window server directly.

**Relevance to Nexus:**
- yabai proves that private CGS APIs exist for window operations that public AX APIs can't do (space management, window layers, opacity).
- The SIP-disabling requirement makes this impractical for Nexus (we can't ask users to disable SIP).
- However, the *public* AX APIs yabai uses for basic window management are the same ones Nexus uses.
- yabai's CLI interface (`yabai -m query --windows`) is a useful reference for window query schemas.

---

### skhd

- **URL:** https://github.com/koekeishiya/skhd
- **Stars:** ~6.7k (estimated)
- **Language:** C
- **License:** MIT

**What it does:** Simple hotkey daemon for macOS. Maps key combinations to shell commands.

**How it hooks into macOS:**
- Uses **CGEventTap** (via `CGEventTapCreate`) to intercept keyboard events globally.
- Requires **Accessibility permission** (not Input Monitoring -- the CGEventTap approach uses the AX privilege).
- When Secure Keyboard Entry is enabled (e.g., in password fields), skhd cannot receive events.
- Config is a simple DSL: `ctrl + alt - h : yabai -m window --focus west`

**Technical details:**
- PID file at `/tmp/skhd_$USER.pid` ensures single instance.
- Executes commands via `$SHELL -c` (defaults to `/bin/bash`).
- Supports modes (like vim modes) for context-dependent keybindings.
- Hot-reloads config without restart.

**Relevance to Nexus:**
- Shows the clean way to intercept global keyboard events on macOS: CGEventTap.
- Nexus doesn't need global hotkeys currently, but if we add "wait for key press" or trigger-based automation, CGEventTap is the mechanism.
- The config DSL is a good reference for action-to-command mapping syntax.

---

## 2. Command-Line & Low-Level Tools

### cliclick

- **URL:** https://github.com/BlueM/cliclick
- **Stars:** ~800+ (estimated)
- **Language:** Objective-C
- **License:** BSD

**What it does:** Command-line tool for simulating mouse and keyboard events on macOS.

**Implementation approach:**
- Uses **CGEventCreateMouseEvent** and **CGEventCreateKeyboardEvent** (Core Graphics event APIs) for input simulation.
- Written in pure Objective-C, compiled as a native binary.
- Requires Accessibility permission for the terminal running it.

**Commands:**
- `c:X,Y` -- click at coordinates
- `dc:X,Y` -- double-click
- `rc:X,Y` -- right-click
- `t:text` -- type text
- `kp:key` -- key press
- `m:X,Y` -- move mouse
- `dd:X,Y` -- drag down (start drag)
- `du:X,Y` -- drag up (end drag)
- `w:ms` -- wait

**Relevance to Nexus:**
- Validates that CGEvent APIs are the right approach for low-level input simulation (same as what pyautogui uses on macOS).
- The command syntax is clean and could inspire improvements to Nexus's `do()` action chains.
- Being a native binary, it may be faster than pyautogui for rapid input sequences -- could be used as a subprocess.

---

### pyautogui

- **URL:** https://github.com/asweigart/pyautogui
- **Stars:** ~10.5k
- **Language:** Python
- **License:** BSD

**What it does:** Cross-platform GUI automation for Python. Controls mouse and keyboard programmatically.

**macOS implementation (`_pyautogui_osx.py`):**
- Uses **Quartz.CGEventPost** with `kCGHIDEventTap` for mouse events.
- Uses **Quartz.CGEventCreateKeyboardEvent** for keyboard events.
- Screenshots use the `screencapture` command (shells out).
- Image location via pyscreeze (pixel matching).
- Requires Accessibility permission.

**Relevance to Nexus:**
- Nexus already uses pyautogui as its fallback input method in `act/input.py`.
- pyautogui is coordinate-based (no accessibility awareness), which is why Nexus layers AX resolution on top.
- pyautogui's `locateOnScreen()` (image-based element finding) could complement AX tree search for apps with poor accessibility.

---

## 3. Commercial / Closed-Source Tools

### Keyboard Maestro

- **URL:** https://www.keyboardmaestro.com/
- **Version:** 11.0.4
- **Price:** $36
- **Platform:** macOS only

**What it does:** The most powerful macro automation tool for macOS. Visual macro builder with hundreds of built-in actions.

**Techniques used:**
- **Accessibility API** for reading UI elements, clicking buttons, and querying state.
- **Image recognition** for finding UI elements by screenshot (takes a screenshot of a button and searches the screen for it).
- **OCR** via Apple Vision framework (VNRecognizeTextRequest) and Tesseract. Can read text from screen regions, images, or clipboard.
- **AppleScript / JXA** execution for app-specific scripting.
- **CGEvent** for keyboard/mouse simulation.
- **Shell scripts** for command-line operations.
- **GUI scripting** (System Events AppleScript) as a fallback.

**Unique capabilities:**
- "Found Image" condition -- searches screen for a reference image, returns coordinates. This is how it handles apps with no accessibility tree.
- Clipboard history with searchable entries.
- Variables, conditionals, loops, subroutines, error handling -- it's a full programming environment in a visual interface.
- "Pause Until" conditions that wait for a specific image, window, or element to appear.

**Relevance to Nexus:**
- The **image recognition approach** is directly relevant to Nexus's "blind Electron apps" problem. When AX tree is empty, searching for a screenshot of a button is a viable fallback.
- **OCR** via Apple Vision could replace or supplement accessibility text extraction for apps with poor AX support.
- The "Pause Until" pattern is similar to Nexus's `wait for <element>` / `wait until <X>` implementation.
- KM's multi-technique approach (AX first, image fallback, OCR fallback) is the same layered strategy Nexus should adopt.

---

## 4. Apple's Own Automation Stack

### AppleScript

- **Status:** Actively maintained by Apple, decades of development.
- **Approach:** English-like scripting language using Apple Events (inter-application communication).

**Key capabilities:**
- Send commands to applications via their scripting dictionaries.
- "GUI Scripting" via System Events -- can click buttons, read menus, interact with UI elements by accessibility properties.
- Direct access to some app internals (Finder, Safari, Mail, etc. have rich scripting dictionaries).

**Limitations:**
- Verbose, hard to parse programmatically.
- No regex, poor string handling.
- GUI scripting is slow and brittle.
- Cannot access apps without scripting dictionaries except through UI scripting.

### JXA (JavaScript for Automation)

- **Status:** Introduced in OS X Yosemite (2014). **Effectively abandoned by Apple** -- no updates since initial release.
- **Documentation:** Sparse, half-finished by Apple.

**Capabilities vs AppleScript:**
- Same underlying Open Scripting Architecture (OSA) -- same capabilities.
- JavaScript syntax instead of English-like syntax.
- Better string handling, regex support, modern language features.
- Can call ObjC APIs via `ObjC.import()` bridge.
- Interoperates with AppleScript libraries.

**Limitations vs AppleScript:**
- Worse documentation and community support.
- Some APIs have rough edges that work in AppleScript but not in JXA.
- Most community code samples are in AppleScript, making conversion nontrivial.
- Apple seems to have abandoned development entirely.

**Relevance to Nexus:**
- Nexus uses AppleScript via `osascript` for specific operations (app activation, Safari control, window geometry queries).
- JXA could replace some of these AppleScript calls with cleaner JavaScript, but the ObjC bridge in JXA gives no advantage over pyobjc (which is more direct).
- The `steipete/macos-automator-mcp` project shows a knowledge base of 200+ AppleScript/JXA automations -- useful reference.

### Apple Shortcuts

- **URL:** Built into macOS Monterey+
- **CLI:** `shortcuts run "Shortcut Name"` -- runs from command line

**Programmatic triggering:**
- `shortcuts run <name>` -- run a shortcut from Terminal.
- `shortcuts run <name> -i <file>` -- pass input file.
- `shortcuts run <name> -o <file>` -- capture output to file.
- `shortcuts list` -- list all shortcuts.
- Can be triggered via `launchd`, cron, or other schedulers.
- URL scheme: `shortcuts://run-shortcut?name=<name>&input=<text>`

**Limitations:**
- Shortcuts that require user interaction (alerts, input dialogs) pause the CLI process.
- No official API for creating/modifying shortcuts programmatically.
- Third-party apps can only define shortcut *actions*, not trigger arbitrary shortcuts.
- Limited automation building blocks compared to KM or Hammerspoon.

**Relevance to Nexus:**
- Nexus could invoke user-defined Shortcuts via `shortcuts run` for pre-built automation sequences.
- The "Run Shell Script" action in Shortcuts could call Nexus as a backend.
- Not a replacement for Nexus's approach, but a complementary integration point.

### Accessibility Inspector

- **URL:** Built into Xcode (`Xcode > Open Developer Tool > Accessibility Inspector`)
- **Private entitlement:** `com.apple.private.accessibility.inspection`

**What it reveals:**
- Full accessibility tree for any app with element hierarchy, roles, subroles, attributes, actions.
- AXTextMarker support for rich text navigation (undocumented in public docs).
- AXWebArea elements for web content within native apps (Safari, Books, etc.) -- complex API not shown in public docs.
- Real-time attribute inspection and action execution.
- Audit tab for accessibility compliance checking.

**Undocumented APIs it uses:**
- Private entitlement allows accessing UI elements that normal apps can't.
- Advanced text APIs (AXTextMarker, AXTextMarkerRange) for precise text selection and navigation.
- The Inspector shows attributes and actions that aren't documented in Apple's public accessibility guides.

**Relevance to Nexus:**
- Essential development tool for understanding what AX attributes are available for specific apps.
- The AXTextMarker APIs are powerful for text-heavy apps but are undocumented and complex.
- The private entitlement means some Inspector features are Apple-only -- we can't replicate them.

---

## 5. Python Libraries for macOS Accessibility

### pyobjc

- **URL:** https://github.com/ronaldoussoren/pyobjc
- **PyPI:** https://pypi.org/project/pyobjc/
- **Stars:** ~2k
- **Latest:** v12.1 (Nov 2025)
- **License:** MIT

**What it is:** The official Python-to-Objective-C bridge. Provides wrappers for all public macOS frameworks including ApplicationServices (AXUIElement), Quartz (CGEvent, screenshots), and Cocoa (NSWorkspace, etc.).

**Key framework wrappers for automation:**
- `pyobjc-framework-ApplicationServices` -- AXUIElement*, CGEvent*
- `pyobjc-framework-Quartz` -- CGWindowListCreateImage (screenshots), CGEvent (input)
- `pyobjc-framework-Cocoa` -- NSWorkspace (app management), NSRunningApplication
- `pyobjc-framework-Accessibility` -- Higher-level Accessibility framework wrappers

**Relevance to Nexus:**
- **Nexus's foundation.** All of Nexus's accessibility and input code is built on pyobjc.
- Actively maintained, supports Python 3.12, macOS 15+.
- The most direct way to access macOS C APIs from Python.

---

### atomacos (fork of pyatom/atomac)

- **URL:** https://github.com/daveenguyen/atomacos
- **Original:** https://github.com/pyatom/pyatom
- **OpenAdapt fork:** https://github.com/OpenAdaptAI/atomacos
- **PyPI:** https://pypi.org/project/atomacos/
- **Latest:** 3.3.0
- **License:** GPL

**What it is:** Python library for macOS GUI automation via Accessibility API. Higher-level than raw pyobjc.

**Approach:**
- Wraps AXUIElement via pyobjc into a `NativeUIElement` class.
- Provides `findAll()`, `findFirst()` with attribute-based queries.
- Recursive search methods (e.g., `windowsR()` finds nested windows).
- Read/write most accessibility attributes.
- Can perform accessibility actions (press, set value, etc.).

**Status:**
- Original pyatom abandoned since 2013.
- atomacos fork created for Python 3 compatibility.
- OpenAdaptAI maintains another fork.
- Low activity -- not a vibrant project.

**Relevance to Nexus:**
- Nexus does everything atomacos does, but better (intent parsing, spatial resolution, caching, observation).
- Could study atomacos's recursive search implementation for edge cases.
- The GPL license makes it incompatible with Nexus's approach if code were borrowed directly.

---

### pyax

- **URL:** https://github.com/eeejay/pyax
- **Blog:** https://blog.monotonous.org/2026/01/12/macos-accessibility-with-pyax/
- **License:** Unknown

**What it is:** A lightweight Python client library for macOS accessibility with command-line tool for diagnostics.

**Approach:**
- Built on pyobjc's accessibility bindings.
- Provides CLI for quick accessibility tree inspection.
- Installable via pip: `pip install pyax[highlight]`
- Created by Eitan Isaacson (Mozilla accessibility engineer).

**Relevance to Nexus:**
- Very recent (Jan 2026 blog post) -- shows ongoing interest in Python AX tooling.
- Good reference for clean pyobjc accessibility wrappers.
- Could complement Nexus for debugging/diagnostic use cases.

---

### macapptree (MacPaw)

- **URL:** https://github.com/MacPaw/macapptree
- **PyPI:** https://pypi.org/project/macapptree/
- **License:** Unknown

**What it is:** Python package that extracts the accessibility tree of macOS applications in JSON format with optional labeled screenshot output.

**Key feature:**
- `get_tree_screenshot()` returns: accessibility tree (JSON), cropped app screenshot, and labeled screenshot with bounding boxes colored by element type.
- Used in MacPaw's Screen2AX research for training vision models on macOS UI.

**Relevance to Nexus:**
- The labeled bounding box screenshot is a brilliant idea for debugging and for vision model training.
- Could inspire a `see(debug=True)` mode that overlays element labels on screenshots.
- MacPaw's research on parsing macOS UI (https://research.macpaw.com/publications/how-to-parse-macos-app-ui) is highly relevant.

---

## 6. Anthropic Computer Use & Official Ports

### Anthropic Computer Use (Official)

- **API Docs:** https://docs.anthropic.com/en/docs/agents-and-tools/computer-use
- **Demo Code:** https://github.com/anthropics/claude-quickstarts/tree/main/computer-use-demo
- **Header:** `anthropic-beta: computer-use-2025-01-24`

**How it works:**
- Claude receives screenshots and returns mouse/keyboard actions as structured tool calls.
- The official demo runs **Linux** (Ubuntu) inside a Docker container.
- Uses Xvfb (virtual X11 display), Mutter (window manager), and xdotool/xdg-utils for input.
- Screenshot-based -- Claude counts pixels and specifies coordinates.
- No accessibility tree integration -- purely visual.

**macOS limitations:**
- The official demo is Linux-only.
- macOS has no Xvfb equivalent (though ScreenCaptureKit and CGEvent provide similar primitives).
- Higher screen resolution on macOS causes coordinate precision issues.

### Claude Cowork

- **Announced:** January 12, 2026
- **Approach:** Runs inside macOS VM using Apple's Virtualization Framework.
- **Security model:** Folder-permission model (read/write/create access to specific directories).
- **Isolation:** Virtual machine sandbox, separate from host OS.

### deedy/mac_computer_use

- **URL:** https://github.com/deedy/mac_computer_use
- **Stars:** ~3k+ (estimated)

**What it is:** Community fork of Anthropic's Computer Use demo adapted for macOS.

**Implementation:**
- Uses **pyautogui** for mouse/keyboard simulation.
- Uses **screencapture** or PIL for screenshots.
- Runs natively on macOS (no Docker).
- Agentic loop: screenshot -> Claude API -> execute action -> repeat.
- Supports macOS Sonoma 15.7+.

**Relevance to Nexus:**
- Shows the minimal viable approach: screenshots + pyautogui coordinates.
- No accessibility tree = same "blind Electron" problem Nexus faces.
- Nexus's approach (AX tree + intent parsing) is strictly superior for apps with accessibility.

### PallavAg/claude-computer-use-macos

- **URL:** https://github.com/PallavAg/claude-computer-use-macos
- **Stars:** ~500+ (estimated)

**What it is:** Another macOS port of Anthropic's Computer Use.

**Implementation:**
- pyautogui for mouse/keyboard.
- screencapture for screenshots.
- Requires Accessibility permission for the terminal.
- Simple command-line or script-based execution.

### newideas99/Anthropic-Computer-Use-MacOS

- **URL:** https://github.com/newideas99/Anthropic-Computer-Use-MacOS
- **Stars:** ~200+ (estimated)

**What it is:** Adapted from Anthropic Quickstarts, modified for macOS.

---

## 7. MCP Servers for macOS

### steipete/macos-automator-mcp

- **URL:** https://github.com/steipete/macos-automator-mcp
- **NPM:** @steipete/macos-automator-mcp
- **Language:** TypeScript/Node.js
- **Author:** Peter Steinberger (prominent iOS/macOS developer)

**What it does:** MCP server that runs AppleScript and JXA scripts on macOS.

**Key features:**
- 200+ pre-built automation scripts in a knowledge base.
- Peers into application accessibility trees via AppleScript System Events.
- Supports inline scripts, script files, and knowledge-base IDs.
- Lazy-loaded knowledge base for fast startup.
- Output formatting modes (auto, human-readable, JSON).

**Relevance to Nexus:**
- The AppleScript/JXA knowledge base is a valuable reference for common automation tasks.
- Complementary approach: Nexus uses native AX APIs; this uses AppleScript wrappers.
- The 200+ scripts represent years of macOS automation patterns distilled.

### steipete/Peekaboo

- **URL:** https://github.com/steipete/Peekaboo
- **NPM:** @steipete/peekaboo-mcp
- **Language:** Swift
- **Author:** Peter Steinberger
- **Version:** 3.x

**What it does:** macOS CLI and MCP server for screenshots + visual question answering + GUI automation.

**Key features (v3):**
- Pixel-accurate window/screen/menu bar captures with optional Retina 2x scaling.
- Full GUI automation: see, click, type, press, scroll, hotkey, swipe.
- Multi-screen capture support.
- Natural-language agent flows for multi-step tasks.
- Multi-provider AI: GPT-5.1, Claude 4.x, Grok 4-fast (vision), Gemini 2.5, local Ollama.
- Both CLI and MCP server modes.

**Relevance to Nexus:**
- **Direct competitor.** Peekaboo v3 does screenshots + clicks + AI -- very similar to Nexus.
- Written in Swift (native), which may have performance advantages for screenshot capture.
- The multi-provider AI integration for visual QA is something Nexus doesn't do (Nexus relies on the AI calling the tools, not providing its own AI inference).
- Different philosophy: Peekaboo is screenshot-first; Nexus is accessibility-tree-first.

### ashwwwin/automation-mcp

- **URL:** https://github.com/ashwwwin/automation-mcp
- **Language:** TypeScript (Bun runtime)

**What it does:** MCP server with mouse, keyboard, screen, and window management.

**Key features:**
- Mouse: click, move, scroll, drag.
- Keyboard: type, send shortcuts.
- Screen: screenshots, color analysis, region highlighting.
- Windows: focus, move, resize, minimize.
- Image matching: wait for images to appear on screen.

**Relevance to Nexus:**
- Coordinate-based approach (no AX tree integration).
- The "wait for image" feature is something Nexus could adopt as a fallback.

### digithree/automac-mcp

- **URL:** https://github.com/digithree/automac-mcp
- **Language:** Python

**What it does:** MCP server for full macOS UI automation.

**Key features:**
- Simulated mouse/keyboard input.
- Window management.
- OCR and native accessibility APIs for text recognition.
- Safari browser automation.
- macOS Spotlight interaction.

**Relevance to Nexus:**
- Python-based like Nexus, uses similar APIs.
- The Spotlight interaction and OCR integration are features Nexus could add.

### mediar-ai/mcp-server-macos-use

- **URL:** https://github.com/mediar-ai/mcp-server-macos-use
- **SDK:** https://github.com/mediar-ai/MacosUseSDK
- **Language:** Swift

**What it does:** MCP server in Swift using macOS accessibility APIs via MacosUseSDK.

**Key features:**
- Open/activate applications.
- Traverse and inspect accessibility trees.
- Simulate mouse clicks.
- Automate workflows via AI commands.
- Works with Claude Desktop, GPT, Gemini.

**Relevance to Nexus:**
- Swift-based, using the same underlying AXUIElement APIs as Nexus.
- The MacosUseSDK is a useful reference for Swift AX wrappers.
- Different architecture (Swift vs Python) but same accessibility foundation.

### baryhuang/mcp-remote-macos-use

- **URL:** https://github.com/baryhuang/mcp-remote-macos-use

**What it does:** MCP server for **remote** macOS control via screen sharing (VNC).

**Key features:**
- Zero setup on target machine -- only screen sharing needs to be enabled.
- Screenshot capture, keyboard input, mouse control over VNC.
- WebRTC support via LiveKit for low-latency streaming.
- Docker-based deployment.

**Relevance to Nexus:**
- Shows how to extend macOS automation to remote machines.
- VNC/screen sharing approach is fundamentally different from Nexus's local AX approach.
- Could inspire a "remote mode" for Nexus in the future.

### mb-dev/macos-ui-automation-mcp

- **URL:** https://github.com/mb-dev/macos-ui-automation-mcp

**What it does:** macOS UI automation and accessibility testing MCP server.

---

## 8. AI Agents That Control macOS (2024-2026)

### Agent-S (Simular AI)

- **URL:** https://github.com/simular-ai/Agent-S
- **Homepage:** https://www.simular.ai/
- **Stars:** ~9.7k
- **License:** Apache 2.0

**What it is:** Open-source framework for autonomous computer interaction through Agent-Computer Interface.

**Versions:**
- **Agent S1** (Dec 2024): Initial release, macOS/OSWorld/WindowsAgentArena support.
- **Agent S2** (Mar 2025): State-of-the-art CUA, outperforms OpenAI Operator and Claude 3.7 Computer-Use.
- **Agent S3** (2025): Won Best Paper Award at ICLR 2025 Agentic AI workshop.

**Approach:**
- Vision-language model based (screenshot + coordinate prediction).
- Supports Azure OpenAI, Anthropic, vLLM backends.
- Integrates Perplexica API for web search capability.
- Learning from past experiences for improved autonomy.

**Relevance to Nexus:**
- Major competitor in the research space.
- Purely vision-based (no AX tree) -- different approach from Nexus.
- Their benchmarking results and papers are valuable reference points.

### CUA (trycua)

- **URL:** https://github.com/trycua/cua
- **Homepage:** https://cua.ai
- **Stars:** ~10k+ (estimated)
- **License:** Apache 2.0

**What it is:** Open-source infrastructure for Computer-Use Agents with sandboxes, SDKs, and benchmarks.

**Key components:**
- **cua-computer:** SDK for controlling desktop environments.
- **cua-agent:** AI agent framework for computer-use tasks.
- **cuabot:** Multi-agent computer-use sandbox CLI.
- **lume:** macOS/Linux VM management on Apple Silicon using Apple's Virtualization Framework.

**macOS sandbox:**
- Native macOS VMs on Apple Silicon.
- Near-native performance.
- Complete isolation from host OS.
- Programmatic VM management via HTTP API.

**Relevance to Nexus:**
- CUA's sandbox approach (VMs) is very different from Nexus's direct-access approach.
- Lume's macOS VM management could enable "safe mode" Nexus operations.
- Their benchmarking framework could be used to evaluate Nexus.

### browser-use/macOS-use

- **URL:** https://github.com/browser-use/macOS-use
- **Stars:** ~2k+ (estimated)

**What it does:** Makes Mac apps accessible for AI agents. Built by the team behind browser-use.

**Approach:**
- Works best with OpenAI or Anthropic API (also supports Gemini).
- Full desktop access -- can use login credentials, interact with any app and UI component.
- Builds on MLX (Apple's ML framework) for local model support.
- Early stage, varying success rates.

**Relevance to Nexus:**
- Another competitor in the "AI controls macOS" space.
- The MLX integration for local model inference is interesting -- Nexus doesn't run its own models.
- Focus on making *any* app controllable, similar goal to Nexus.

### suitedaces/computer-agent

- **URL:** https://github.com/suitedaces/computer-agent
- **Language:** Tauri + React + Rust

**What it does:** Desktop app for computer control with AI.

**Two modes:**
1. **Computer Use Mode:** Takes over screen, screenshot + mouse/keyboard control.
2. **Background Mode:** Chrome DevTools Protocol + terminal. No mouse/keyboard interference.

**Relevance to Nexus:**
- The two-mode approach is interesting. Nexus is more like "Background Mode" (AX + CDP) but with the ability to do "Computer Use Mode" via pyautogui.
- Built with Tauri/Rust -- different tech stack but same concepts.

### suitedaces/dorabot

- **URL:** https://github.com/suitedaces/dorabot
- **Homepage:** https://www.dora.so/

**What it does:** macOS app for 24/7 AI agent with memory, scheduled tasks, browser automation, and messaging (WhatsApp, Telegram, Slack).

**Key features:**
- Persistent memory.
- Scheduled/autonomous tasks.
- Multi-agent parallelism.
- Local-only, no telemetry.
- macOS native sandbox.

**Relevance to Nexus:**
- The "persistent memory + scheduled tasks" concept aligns with Nexus's memory system.
- Multi-channel messaging integration (WhatsApp, Slack) is a use case Nexus hasn't explored.

### adeelahmad/MacPilot

- **URL:** https://github.com/adeelahmad/MacPilot
- **PyPI:** `pip install macpilot`

**What it does:** AI-powered macOS automation framework with natural language control via GPT models.

**Technical components:**
- GPT-powered instruction analysis.
- UI state tracking and validation.
- Actor system for modular action execution.
- Pattern system for reusable interactions.
- Vision system for UI element detection + OCR.
- Automated error recovery.

**Relevance to Nexus:**
- The "actor system" and "pattern system" concepts could improve Nexus's action pipeline.
- Error recovery system is more sophisticated than Nexus's "Did you mean?" approach.
- Another Python-based project, so code patterns may be directly applicable.

### Open Interpreter

- **URL:** https://github.com/openinterpreter/open-interpreter
- **Homepage:** https://www.openinterpreter.com/
- **Stars:** ~62.3k
- **License:** AGPL-3.0

**What it is:** Natural language interface for computers. LLMs run code (Python, JS, Shell) locally.

**macOS GUI automation:**
- "Computer API" provides `display` (screenshots) and `keyboard`/`mouse` (input simulation).
- New Computer Update Part II (2025): native Mac integrations for calendar, contacts, browser, mail, SMS.
- Local vision model support.
- 5x launch speed improvements.

**Approach:**
- Primarily code-execution based (the LLM writes and runs code).
- GUI automation is secondary to code execution.
- Uses screenshots + coordinate-based interaction for GUI tasks.

**Relevance to Nexus:**
- Massively popular (62k stars) but very different approach.
- OI executes code; Nexus provides structured tools. Different paradigm.
- OI's native Mac integrations (calendar, contacts, etc.) show demand for OS-specific features.
- The Computer API's `display`/`keyboard`/`mouse` abstraction is similar to Nexus's `see`/`do` but less structured.

### showlab/computer_use_ootb

- **URL:** https://github.com/showlab/computer_use_ootb
- **Stars:** ~1.8k

**What it does:** Out-of-the-box GUI Agent for Windows and macOS.

**Key features:**
- Supports Claude 3.5 Computer Use API + local models (ShowUI, UI-TARS).
- ShowUI is an open-source 2B VLA model for GUI agents (CVPR 2025).
- "gpt-4o + ShowUI" is ~200x cheaper than Claude Computer Use.
- Requires M1+ with 16GB RAM for local inference on macOS.
- No Docker required.

**Relevance to Nexus:**
- The local VLA model approach (ShowUI) could complement Nexus for vision-based fallback.
- 200x cost reduction vs Claude is significant for frequent automation.

### niuzaisheng/ScreenAgent

- **URL:** https://github.com/niuzaisheng/ScreenAgent

**What it is:** VLM-driven computer control agent (IJCAI-24 paper). Observes screenshots, plans actions, executes via mouse/keyboard, reflects on results.

### elfvingralf/macOSpilot-ai-assistant

- **URL:** https://github.com/elfvingralf/macOSpilot-ai-assistant

**What it does:** Voice + vision AI assistant. Takes screenshot of active window, records voice question, sends both to OpenAI APIs (Whisper + Vision + TTS).

**Approach:**
- NodeJS/Electron app.
- Keyboard shortcut triggers screenshot + recording.
- Uses OpenAI Whisper (speech-to-text), Vision (screenshot analysis), TTS (response audio).
- Read-only -- answers questions about what's on screen but doesn't control the computer.

### chidiwilliams/GPT-Automator

- **URL:** https://github.com/chidiwilliams/GPT-Automator

**What it does:** Voice-controlled Mac assistant. Proof-of-concept.

**Approach:**
- Whisper for voice-to-text.
- GPT-3 generates AppleScript (desktop) or JavaScript (browser) from natural language.
- Executes the generated script.
- PyQt6 GUI.

**Relevance to Nexus:**
- Shows the "LLM generates AppleScript" approach. This is fragile but sometimes effective.
- Nexus's structured intent parsing is more reliable than generated scripts.

### askui/vision-agent

- **URL:** https://github.com/askui/vision-agent
- **Homepage:** https://www.askui.com/

**What it does:** Enterprise computer-use agent infrastructure for desktop, mobile, and HMI devices.

**Key features:**
- Agent OS: device controller for screenshots, mouse, keyboard across any OS.
- Tool Store: extensible tool system for agent capabilities.
- Multi-provider AI: Anthropic, OpenRouter, Hugging Face, etc.
- Supports Windows, macOS, Linux, Android, iOS.
- Vision-based (no accessibility tree).

**Relevance to Nexus:**
- Enterprise-focused competitor.
- Cross-platform support is broader than Nexus.
- Vision-only approach contrasts with Nexus's AX-first approach.

### OpenAdaptAI/OpenAdapt

- **URL:** https://github.com/OpenAdaptAI/OpenAdapt
- **Homepage:** https://openadapt.ai/

**What it does:** Open-source Generative Process Automation. Record human demonstrations, train models, deploy replay agents.

**Approach:**
- Record: capture screenshots, mouse/keyboard events, accessibility state during human task execution.
- Train: use vision-language models to understand the recorded workflow.
- Deploy: replay the workflow with adaptive strategies (simple replay, GPT-4 guided, vision model guided).
- Privacy: built-in PII/PHI scrubbing.

**macOS support:**
- Requires Accessibility, Screen Recording, and Input Monitoring permissions.
- Uses atomacos fork for accessibility tree access.

**Relevance to Nexus:**
- The "record then replay" paradigm is fundamentally different from Nexus's "intent then execute" paradigm.
- Their atomacos fork shows ongoing need for Python AX libraries.
- The adaptive replay strategies (GPT-4 guided) bridge the two approaches.

---

## 9. Research & Academic Projects

### MacPaw Screen2AX

- **Paper:** https://arxiv.org/html/2507.16704v1
- **Research page:** https://research.macpaw.com/publications/screen2axvisionbasedapproachautomatic

**What it is:** Vision-based approach for automatic macOS accessibility metadata generation.

**Approach:**
- Trains a model to predict accessibility properties from screenshots alone.
- Uses macapptree to collect ground truth accessibility data from 112 macOS apps.
- Goal: generate accessibility metadata for apps that lack it.

**Relevance to Nexus:**
- Directly addresses Nexus's "blind Electron apps" problem.
- If a model can predict AX properties from screenshots, Nexus could use it as a fallback when real AX tree is empty.

### MacPaw GUIrilla

- **Research page:** https://research.macpaw.com/publications/guirilla-scalable-framework-automated

**What it is:** Scalable framework for automated desktop UI exploration.

### UiPad Dataset (MacPaw)

- **URL:** https://huggingface.co/datasets/macpaw-research/UiPad

**What it is:** macOS UI dataset on Hugging Face for training GUI agents.

---

## 10. Curated Lists & Meta-Resources

### Awesome-Gui-Agents

- **URL:** https://github.com/supernalintelligence/Awesome-Gui-Agents
- Comprehensive list of GUI agents (browser and computer use).

### Awesome Computer Use

- **URL:** https://github.com/ranpox/awesome-computer-use
- Collection of resources for computer-use GUI agents.

### Awesome GUI Agents (ZJU-REAL)

- **URL:** https://github.com/ZJU-REAL/Awesome-GUI-Agents
- Curated collection of resources, tools, and frameworks.

### Awesome GUI Agent (showlab)

- **URL:** https://github.com/showlab/Awesome-GUI-Agent
- Papers and resources for multi-modal GUI agents.

### ACU (trycua)

- **URL:** https://github.com/trycua/acu
- Curated list of resources about AI agents for Computer Use.

### Awesome UI Agents (OpenDILab)

- **URL:** https://github.com/opendilab/awesome-ui-agents
- Covers Web, App, OS, and beyond.

---

## 11. Key Takeaways for Nexus

### What Nexus Already Does Better Than Most

1. **Accessibility-first approach.** Most competing projects (Agent-S, CUA, computer-agent, macOS-use, all Anthropic ports) are screenshot+coordinate based. Nexus's AX tree parsing gives structural understanding that screenshot-only approaches lack.

2. **Intent parsing.** Nexus's `do("click Save")` is more natural and reliable than coordinate-based `click(543, 287)`. No other MCP server has comparable intent resolution.

3. **Three-tool simplicity.** Most competitors expose 10-40 individual tools. Nexus's see/do/memory trinity is uniquely minimalist.

4. **Observation mode.** Real-time AXObserver integration is rare. Only Hammerspoon's hs.axuielement.observer offers comparable functionality.

5. **CDP integration.** Seamless Chrome web content in the same `see()` call is a differentiator.

### What Nexus Should Learn From / Adopt

1. **Vision fallback (from Keyboard Maestro, ShowUI, Screen2AX):**
   - When AX tree is empty, use image recognition or OCR as fallback.
   - Apple's VNRecognizeTextRequest for on-device OCR is free and fast.
   - MacPaw's Screen2AX model could predict AX properties from screenshots.

2. **Labeled screenshots (from macapptree):**
   - Add `see(debug=True)` or `see(annotated=True)` that returns a screenshot with bounding boxes overlaid on each AX element.
   - Invaluable for debugging and for training/prompting vision models.

3. **AppleScript/JXA knowledge base (from steipete/macos-automator-mcp):**
   - 200+ pre-built scripts for common macOS tasks.
   - Could integrate these as "recipes" Nexus falls back to.

4. **Image matching (from Keyboard Maestro, automation-mcp):**
   - "Wait for image" and "find image on screen" as fallback for apps with no AX tree.
   - OpenCV template matching or Apple Vision VNRecognizeImageRequest.

5. **VM sandboxing (from CUA/Lume, Claude Cowork):**
   - For unsafe operations, running in a macOS VM provides isolation.
   - Apple's Virtualization Framework makes this native and fast on Apple Silicon.

6. **Private API awareness (from yabai):**
   - yabai's CGSConnection injection shows what's possible but impractical for Nexus.
   - However, understanding what CGS APIs exist helps know the limits of public APIs.

7. **Multi-provider AI (from Peekaboo v3):**
   - Peekaboo v3 supports 5+ AI providers for visual QA.
   - Nexus doesn't need to run its own inference, but could offer an optional "visual fallback" mode.

### Competitive Landscape Summary

| Project | Approach | AX Tree | Vision | MCP | Stars |
|---------|----------|---------|--------|-----|-------|
| **Nexus** | AX + CDP + pyautogui | Yes (primary) | Screenshots | Yes | -- |
| Peekaboo v3 | Screenshots + AX + AI | Partial | Primary | Yes | ~1k |
| macos-automator-mcp | AppleScript/JXA | Via System Events | No | Yes | ~2k |
| automation-mcp | Coordinates + screenshots | No | Primary | Yes | ~500 |
| automac-mcp | OCR + AX + mouse/kb | Partial | OCR | Yes | ~200 |
| mcp-server-macos-use | Swift AX SDK | Yes | No | Yes | ~500 |
| Agent-S | Vision-language model | No | Primary | No | ~9.7k |
| CUA (trycua) | VM sandbox + SDK | No | Primary | No | ~10k |
| macOS-use | Screenshot + coordinates | No | Primary | No | ~2k |
| computer-agent | Screenshots + CDP | No | Primary | No | ~2k |
| Open Interpreter | Code execution | No | Optional | No | ~62k |
| ShowUI/OOTB | Local VLA model | No | Primary | No | ~1.8k |
| MacPilot | GPT + vision + AX | Partial | Yes | No | ~300 |
| Hammerspoon | Lua scripting + full AX | Yes | No | No | ~14.5k |
| Keyboard Maestro | AX + image + OCR | Yes | Yes | No | Commercial |

### Nexus's Unique Position

Nexus is the only project that combines:
- Native AXUIElement tree walking (not AppleScript wrapping)
- Intent-based action resolution ("click Save" not coordinates)
- Chrome CDP web content integration
- Real-time AXObserver change detection
- Persistent memory system
- All wrapped in just 3 MCP tools

The closest competitor is Peekaboo v3, but it's screenshot-first while Nexus is accessibility-first. The next move for Nexus should be adding vision fallbacks (OCR, image matching) for the cases where AX tree fails (system dialogs, blind Electron apps), which would make it the most complete macOS automation solution in the space.

---

*Research compiled Feb 24, 2026 for the Nexus project.*
