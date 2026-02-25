---
name: terminal
description: When to use Terminal GUI vs shell commands, iTerm2 patterns
requires: []
---

# Terminal Skill

If you're an AI agent with shell access (Bash tool), you almost never need to automate Terminal.app via Nexus GUI. This skill clarifies when to use each approach.

## Decision Tree

```
Can you run the command directly via Bash tool?
  YES → Use Bash. Do not touch Terminal.app.
  NO  → Is it interactive (needs a TTY, prompts, ncurses)?
    YES → Use Terminal.app via Nexus or AppleScript
    NO  → Use Bash.
```

## When to Use Terminal GUI (via Nexus)

- Interactive tools: `htop`, `vim`, `nano`, `less`, `ssh` sessions
- Commands that need a persistent TTY
- When the user explicitly wants to see something in their terminal
- Monitoring running processes (tail -f, watch, etc.)

## When NOT to Use Terminal GUI

- Any non-interactive command — use Bash tool directly
- File operations — use Bash, Read, Write, Glob tools
- Git operations — use Bash tool
- Package management — use Bash tool

## Opening Terminal and Running Commands

```bash
# Open Terminal.app
open -a Terminal

# Open Terminal at a specific directory
open -a Terminal /path/to/dir

# Run a command in a new Terminal window
osascript -e 'tell app "Terminal" to do script "ls -la ~/Desktop"'

# Run in a new tab of existing window
osascript -e 'tell app "Terminal" to do script "top" in front window'
```

## iTerm2 (if installed)

```bash
# Open iTerm2
open -a iTerm

# Run command in new iTerm tab
osascript -e '
tell app "iTerm2"
    tell current session of current window
        write text "ls -la"
    end tell
end tell'

# New iTerm window with command
osascript -e '
tell app "iTerm2"
    create window with default profile command "htop"
end tell'
```

## Terminal Keyboard Shortcuts

```
do("press cmd+t")         # New tab
do("press cmd+n")         # New window
do("press cmd+w")         # Close tab
do("press cmd+k")         # Clear screen
do("press ctrl+c")        # Interrupt (SIGINT)
do("press ctrl+d")        # EOF (exit shell)
do("press ctrl+z")        # Suspend process
do("press ctrl+l")        # Clear screen
do("press ctrl+r")        # Reverse search history
do("press ctrl+a")        # Beginning of line
do("press ctrl+e")        # End of line
```

## Tips

- The Bash tool runs commands directly — it doesn't need Terminal.app
- If you need persistent background processes: `nohup cmd &` or `tmux`
- `screen` and `tmux` require a real TTY — use Terminal.app for those
- Terminal.app on Spanish macOS is still called "Terminal"
- iTerm2 has richer AppleScript support than Terminal.app
