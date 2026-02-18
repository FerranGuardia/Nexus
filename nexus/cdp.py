"""CDP — connect to Chrome via DevTools Protocol.

Context managers: connect/disconnect per call. Simple and stateless.
"""

import sys
from contextlib import contextmanager

CDP_URL = "http://localhost:9222"

@contextmanager
def cdp_page(url: str = CDP_URL):
    """Connect to Chrome CDP → yield the active page → disconnect.

    Usage:
        with cdp_page() as page:
            title = page.title()
    """
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    try:
        browser = pw.chromium.connect_over_cdp(url)
    except Exception as e:
        pw.stop()
        print('{"ok": false, "error": "Cannot connect to Chrome CDP. Launch Chrome with --remote-debugging-port=9222", "details": "%s"}' % str(e).replace('"', '\\"'), file=sys.stderr)
        sys.exit(1)

    contexts = browser.contexts
    if not contexts or not contexts[0].pages:
        browser.close()
        pw.stop()
        print('{"ok": false, "error": "No browser tabs found"}', file=sys.stderr)
        sys.exit(1)

    page = contexts[0].pages[0]
    try:
        yield page
    finally:
        browser.close()
        pw.stop()


@contextmanager
def cdp_browser(url: str = CDP_URL):
    """Connect to Chrome CDP → yield (page, browser) → disconnect.

    For commands that need browser-level access (e.g. listing all tabs).
    """
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    try:
        browser = pw.chromium.connect_over_cdp(url)
    except Exception as e:
        pw.stop()
        print('{"ok": false, "error": "Cannot connect to Chrome CDP. Launch Chrome with --remote-debugging-port=9222", "details": "%s"}' % str(e).replace('"', '\\"'), file=sys.stderr)
        sys.exit(1)

    contexts = browser.contexts
    if not contexts or not contexts[0].pages:
        browser.close()
        pw.stop()
        print('{"ok": false, "error": "No browser tabs found"}', file=sys.stderr)
        sys.exit(1)

    page = contexts[0].pages[0]
    try:
        yield page, browser
    finally:
        browser.close()
        pw.stop()
