---
name: vscode
description: VS Code automation — focus-stealing workaround, Command Palette, Electron quirks
requires: []
---

# VS Code Skill

VS Code is an Electron app. It has a deep AX tree (depth 14-20) and steals focus when hosting MCP servers. Prefer keyboard shortcuts and Command Palette.

## Critical: Focus-Stealing

VS Code hosts the Nexus MCP server, so it steals focus on every MCP call. Mitigations:

- Always use `app=` parameter: `do("click Save", app="Safari")`
- Nexus auto-restores focus after 0.4s for actions with `app=` param
- For rapid multi-step actions in other apps, chain them: `do("click A; click B; click C", app="Safari")`

## Command Palette (fastest way to do anything)

```
do("press cmd+shift+p")              # Open Command Palette
do("press cmd+shift+p"); do("type format document")  # Then type command
```

Common palette commands (type after Cmd+Shift+P):
- `>Preferences: Open Settings` — open settings
- `>Terminal: Create New Terminal` — new terminal
- `>View: Toggle Sidebar Visibility` — toggle sidebar
- `>Git: Commit` — git commit
- `>File: Save All` — save all files

## Keyboard Shortcuts (no tree walk needed)

```
do("press cmd+s")            # Save
do("press cmd+shift+s")      # Save As
do("press cmd+p")            # Quick Open (go to file)
do("press cmd+shift+p")      # Command Palette
do("press cmd+,")            # Settings
do("press cmd+b")            # Toggle sidebar
do("press cmd+j")            # Toggle panel/terminal
do("press ctrl+`")           # Toggle terminal
do("press cmd+shift+e")      # Explorer
do("press cmd+shift+f")      # Search across files
do("press cmd+shift+g")      # Source Control
do("press cmd+shift+x")      # Extensions
do("press cmd+shift+d")      # Debug
do("press cmd+\\")           # Split editor
do("press cmd+1")            # Focus first editor group
do("press cmd+2")            # Focus second editor group
do("press cmd+w")            # Close tab
do("press cmd+shift+t")      # Reopen closed tab
do("press cmd+k cmd+s")      # Keyboard Shortcuts editor
do("press cmd+shift+n")      # New window
do("press cmd+f")            # Find
do("press cmd+h")            # Find and replace
do("press cmd+g")            # Go to line
do("press cmd+d")            # Select next occurrence
do("press cmd+shift+l")      # Select all occurrences
do("press option+up")        # Move line up
do("press option+down")      # Move line down
do("press cmd+shift+k")      # Delete line
do("press cmd+/")            # Toggle comment
do("press cmd+shift+7")      # Toggle comment (Spanish keyboard)
```

## Electron AX Tree Quirks

- Nexus auto-enables AXManualAccessibility for VS Code (`com.microsoft.VSCode`)
- Tree depth goes to 14-20 — Nexus uses max_depth=20 for Electron apps
- Content nests deep: Window → WebArea → groups → ... → actual elements
- Always use `see(query="...")` — the full tree is enormous
- After first enable, there's a ~2s delay while Chromium builds the tree

## CLI Alternatives (skip GUI entirely)

```bash
# Open file at specific line
code --goto /path/to/file.py:42

# Open folder
code /path/to/project

# Diff two files
code --diff file1.py file2.py

# Install extension
code --install-extension ms-python.python

# List extensions
code --list-extensions

# Open settings JSON
code ~/Library/Application\ Support/Code/User/settings.json
```

## Tips

- The `code` CLI is faster than GUI for opening files and running commands
- Settings sync means changes propagate across machines — be careful
- For Electron debugging: `open -a "Visual Studio Code" --args --force-renderer-accessibility`
- VS Code fires AXTitleChanged ~8/sec — observe mode uses 2s debounce for VS Code
