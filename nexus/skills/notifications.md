---
name: notifications
description: macOS notifications — osascript, terminal-notifier, Notification Center
requires: []
---

# Notifications Skill

Send macOS notifications from the command line. No GUI needed.

## AppleScript (built-in, no install)

```bash
# Simple notification
osascript -e 'display notification "Task complete" with title "Nexus"'

# With subtitle
osascript -e 'display notification "All tests passed" with title "Nexus" subtitle "Test Suite"'

# With sound
osascript -e 'display notification "Build done" with title "Nexus" sound name "Glass"'
```

Available sounds: Basso, Blow, Bottle, Frog, Funk, Glass, Hero, Morse, Ping, Pop, Purr, Sosumi, Submarine, Tink

## Nexus do() (built-in)

```
do("notify Task complete")           # Quick notification
do("say Hello world")                # Text-to-speech
```

## terminal-notifier (more features)

```bash
# Install
brew install terminal-notifier

# Basic
terminal-notifier -title "Nexus" -message "Task complete"

# With subtitle and sound
terminal-notifier -title "Nexus" -subtitle "Build" -message "Success" -sound Glass

# Open URL on click
terminal-notifier -title "PR Ready" -message "Click to view" -open "https://github.com/..."

# Execute command on click
terminal-notifier -title "Deploy" -message "Click to deploy" -execute "make deploy"

# With custom icon
terminal-notifier -title "Nexus" -message "Done" -appIcon /path/to/icon.png

# Group notifications (replace previous)
terminal-notifier -title "Build" -message "Step 2/5" -group "build-progress"

# Remove grouped notification
terminal-notifier -remove "build-progress"
```

## Text-to-Speech

```bash
# Built-in say command
say "Task complete"
say -v Samantha "Hello world"      # Specific voice
say -v "?" | head -20               # List available voices
say -r 200 "Slower speech"          # Rate (words per minute)
say -o /tmp/speech.aiff "Saved"     # Save to file
```

## Tips

- `osascript` notifications are the simplest — no install needed
- `terminal-notifier` supports click actions (open URL, run command) — more powerful
- Notifications respect Do Not Disturb — they'll queue silently
- `say` is useful for audio feedback during long tasks
- On Spanish macOS, notification text can be in any language — no localization issues
