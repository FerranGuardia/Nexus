---
name: apple-shortcuts
description: Apple Notes, Reminders, Calendar and more via Shortcuts CLI and AppleScript
requires: [shortcuts]
---

# Apple Shortcuts Skill

Use the `shortcuts` CLI and `osascript` to interact with Apple apps
without navigating their GUI. These are built into macOS — no install needed.

## When to use

- Quick access to Notes, Reminders, Calendar events
- Automating Apple app workflows
- Running any Shortcuts the user has created

## Shortcuts CLI

```bash
shortcuts list                          # list all shortcuts
shortcuts run "shortcut name"           # run a shortcut
shortcuts run "shortcut name" -i input  # run with input
shortcuts view "shortcut name"          # view shortcut details
```

## Apple Notes (via AppleScript)

```bash
# List all notes (title + folder)
osascript -e 'tell app "Notes" to get {name, name of container} of every note'

# Read a note by title
osascript -e 'tell app "Notes" to get body of note "My Note"'

# Create a note
osascript -e 'tell app "Notes" to make new note at folder "Notes" with properties {name:"Title", body:"Content"}'

# Search notes
osascript -e 'tell app "Notes" to get name of every note whose name contains "search term"'
```

## Apple Reminders (via AppleScript)

```bash
# List all reminder lists
osascript -e 'tell app "Reminders" to get name of every list'

# List reminders in a list
osascript -e 'tell app "Reminders" to get name of every reminder in list "My List"'

# Create a reminder
osascript -e 'tell app "Reminders" to make new reminder in list "My List" with properties {name:"Buy milk", body:"2% organic"}'

# Complete a reminder
osascript -e 'tell app "Reminders" to set completed of reminder "Buy milk" in list "My List" to true'

# Create with due date
osascript -e 'tell app "Reminders" to make new reminder in list "My List" with properties {name:"Meeting prep", due date:date "2026-03-01 09:00:00"}'
```

## Calendar (via AppleScript)

```bash
# List calendars
osascript -e 'tell app "Calendar" to get name of every calendar'

# List today's events
osascript -e 'tell app "Calendar" to get {summary, start date, end date} of every event of calendar "Home" whose start date > (current date) and start date < ((current date) + 1 * days)'

# Create an event
osascript -e '
tell app "Calendar"
  tell calendar "Home"
    make new event with properties {summary:"Lunch", start date:date "2026-03-01 12:00:00", end date:date "2026-03-01 13:00:00"}
  end tell
end tell'
```

## System Automation

```bash
# Toggle dark mode
osascript -e 'tell app "System Events" to tell appearance preferences to set dark mode to not dark mode'

# Get current dark mode state
osascript -e 'tell app "System Events" to get dark mode of appearance preferences'

# Set volume
osascript -e 'set volume output volume 50'

# Get battery
pmset -g batt

# Notification
osascript -e 'display notification "Hello" with title "Nexus"'
```

## Tips

- AppleScript uses the system language — on Spanish macOS, some app names stay English but properties may differ
- `shortcuts` CLI works with any user-created Shortcut — ask the user what they have
- For complex Notes content, HTML is returned — pipe through `textutil -stdin -convert txt -stdout` to get plain text
- Calendar date format depends on locale; ISO 8601 usually works
