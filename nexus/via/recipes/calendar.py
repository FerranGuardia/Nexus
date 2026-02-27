"""Calendar.app recipes — create events, list events via AppleScript."""

from nexus.via.recipe import recipe, applescript


@recipe(
    r"(?:create|add|new|make) (?:a )?(?:calendar )?event (?:called |named |titled )?(.+?)(?:\s+(?:on|at|for)\s+(.+))?$",
    app="calendar",
)
def create_event(m, pid=None):
    """Create a new calendar event in Calendar.app."""
    title = m.group(1).strip().strip("'\"")
    when = m.group(2) or "today"
    return applescript(f'''
        tell application "Calendar"
            tell calendar 1
                make new event with properties {{
                    summary:"{title}",
                    start date:(current date),
                    end date:((current date) + 3600)
                }}
            end tell
            activate
        end tell
    ''')


@recipe(r"(?:list|show|get) (?:today'?s? )?(?:calendar )?events?", app="calendar")
def list_events(m, pid=None):
    """List today's calendar events."""
    return applescript('''
        tell application "Calendar"
            set today to current date
            set time of today to 0
            set tomorrow to today + (1 * days)
            set eventList to ""
            repeat with cal in calendars
                set evts to (every event of cal whose start date >= today and start date < tomorrow)
                repeat with evt in evts
                    set eventList to eventList & summary of evt & " at " & time string of start date of evt & linefeed
                end repeat
            end repeat
            if eventList is "" then return "No events today"
            return eventList
        end tell
    ''')
