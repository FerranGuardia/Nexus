"""Notes.app recipes — create, search, list via AppleScript."""

from nexus.via.recipe import recipe, applescript


@recipe(
    r"(?:create|new|add|make) (?:a )?note (?:called |named |titled )?(.+?)(?:\s+(?:saying|with|content|body)\s+(.+))?$",
    app="notes",
)
def create_note(m, pid=None):
    """Create a new note in Notes.app."""
    title = m.group(1).strip().strip("'\"")
    body = m.group(2) or ""
    return applescript(f'''
        tell application "Notes"
            make new note at folder "Notes" with properties {{
                name:"{title}", body:"{body}"
            }}
            activate
        end tell
    ''')


@recipe(r"(?:search|find) notes? (?:for |about |containing )?(.+)", app="notes")
def search_notes(m, pid=None):
    """Search notes by keyword."""
    query = m.group(1).strip().strip("'\"")
    return applescript(f'''
        tell application "Notes"
            set matches to every note whose name contains "{query}" or body contains "{query}"
            set result to ""
            repeat with n in matches
                set result to result & name of n & linefeed
            end repeat
            if result is "" then return "No notes found for: {query}"
            return result
        end tell
    ''')


@recipe(r"(?:list|show) (?:my |all )?notes", app="notes")
def list_notes(m, pid=None):
    """List recent notes."""
    return applescript('''
        tell application "Notes"
            set noteList to ""
            set noteItems to notes 1 thru (min of {20, count of notes})
            repeat with n in noteItems
                set noteList to noteList & name of n & linefeed
            end repeat
            return noteList
        end tell
    ''')
