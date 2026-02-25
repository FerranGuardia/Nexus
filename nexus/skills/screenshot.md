---
name: screenshot
description: macOS screenshots — screencapture CLI, region capture, annotation
requires: []
---

# Screenshot Skill

Use the `screencapture` CLI for screenshots. No GUI needed.

## CLI Commands

```bash
# Full screen to file
screencapture /tmp/screen.png

# Full screen to clipboard
screencapture -c

# No sound, no flash
screencapture -x /tmp/screen.png

# Specific region (x,y,width,height)
screencapture -x -R 100,200,400,300 /tmp/region.png

# Specific window (interactive — requires click)
screencapture -x -w /tmp/window.png

# Specific window by ID (non-interactive)
screencapture -x -l <windowID> /tmp/window.png

# Timed capture (5 seconds delay)
screencapture -x -T 5 /tmp/delayed.png

# JPEG format with quality (0-100)
screencapture -x -t jpg /tmp/screen.jpg

# PDF format
screencapture -x -t pdf /tmp/screen.pdf

# TIFF format
screencapture -x -t tiff /tmp/screen.tiff
```

## Getting Window IDs for -l Flag

```bash
# Get window ID for a specific app using Python
python3 -c "
from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID
for w in CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID):
    if 'Safari' in w.get('kCGWindowOwnerName', ''):
        print(f\"ID: {w['kCGWindowNumber']} — {w.get('kCGWindowName', '')}\")
"
```

## Keyboard Shortcuts (interactive)

```
Cmd+Shift+3        Full screen screenshot (saves to Desktop)
Cmd+Shift+4        Region selection (drag to capture)
Cmd+Shift+4+Space  Window capture (click a window)
Cmd+Shift+5        Screenshot toolbar (region, window, record)
Ctrl + any above   Copy to clipboard instead of file
```

## Nexus Integration

```
# Nexus can include a screenshot in see() output
see(screenshot=True)

# But for MCP, screenshots are often too large
# Better approach: capture to file, then read with Read tool
```

```bash
screencapture -x /tmp/screen.png
# Then use Read tool on /tmp/screen.png (renders visually)
```

## Annotation (Preview.app)

```bash
# Open screenshot in Preview for annotation
open -a Preview /tmp/screen.png
# Then use Nexus to interact with Preview's markup toolbar
```

## Tips

- `-x` suppresses the camera sound — always use it for automation
- `-R x,y,w,h` captures a specific region without user interaction
- For MCP, always save to file + use Read tool (inline base64 is too large)
- JPEG at quality 50 is a good balance of size and readability for automation
- Window IDs can be found via CGWindowListCopyWindowInfo (Python)
- `screencapture` requires Screen Recording permission on macOS Catalina+
