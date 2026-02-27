"""Mail.app recipes — compose, check, count via AppleScript."""

from nexus.via.recipe import recipe, applescript


@recipe(
    r"(?:send|compose|write|new) (?:an? )?email (?:to )?(.+?)(?:\s+(?:about|saying|subject|with subject|re)\s+(.+))?$",
    app="mail",
)
def compose_email(m, pid=None):
    """Open a new email composition window in Mail.app."""
    to = m.group(1).strip()
    subject = m.group(2) or ""
    script = f'''
        tell application "Mail"
            set msg to make new outgoing message with properties {{
                visible:true, subject:"{subject}"
            }}
            tell msg
                make new to recipient with properties {{address:"{to}"}}
            end tell
            activate
        end tell
    '''
    return applescript(script)


@recipe(r"check (?:my )?(?:email|inbox|mail|messages)", app="mail")
def check_mail(m, pid=None):
    """Check for new email in Mail.app."""
    return applescript('tell application "Mail" to check for new mail')


@recipe(r"(?:how many |count )?unread (?:emails?|messages?|mail)", app="mail")
def unread_count(m, pid=None):
    """Count unread messages in Mail.app."""
    return applescript(
        'tell application "Mail" to return unread count of inbox'
    )
