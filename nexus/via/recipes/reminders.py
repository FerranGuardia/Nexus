"""Reminders.app recipes — add, complete, list via AppleScript."""

from nexus.via.recipe import recipe, applescript


@recipe(
    r"(?:add|create|new|make) (?:a )?reminder (?:to |called |named )?(.+?)(?:\s+(?:due|by|on|for)\s+(.+))?$",
    app="reminders",
)
def add_reminder(m, pid=None):
    """Add a reminder to Reminders.app."""
    title = m.group(1).strip().strip("'\"")
    return applescript(f'''
        tell application "Reminders"
            make new reminder with properties {{name:"{title}"}}
        end tell
    ''')


@recipe(r"(?:list|show) (?:my )?reminders", app="reminders")
def list_reminders(m, pid=None):
    """List incomplete reminders."""
    return applescript('''
        tell application "Reminders"
            set reminderList to ""
            set items to (reminders of default list whose completed is false)
            repeat with r in items
                set reminderList to reminderList & name of r & linefeed
            end repeat
            if reminderList is "" then return "No pending reminders"
            return reminderList
        end tell
    ''')


@recipe(r"(?:complete|finish|done|check off) reminder (.+)", app="reminders")
def complete_reminder(m, pid=None):
    """Mark a reminder as complete."""
    name = m.group(1).strip().strip("'\"")
    return applescript(f'''
        tell application "Reminders"
            set items to (reminders of default list whose name contains "{name}" and completed is false)
            if (count of items) > 0 then
                set completed of item 1 of items to true
                return "Completed: " & name of item 1 of items
            else
                return "No matching reminder found: {name}"
            end if
        end tell
    ''')
