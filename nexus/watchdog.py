"""Watchdog — kills the process after a timeout. No side effects on import."""

import json
import os
import sys
import threading
import time

DEFAULT_TIMEOUT = 30


def start_watchdog(timeout: int = DEFAULT_TIMEOUT):
    """Start a daemon thread that force-kills this process after `timeout` seconds."""
    pid = os.getpid()

    def _die():
        time.sleep(timeout)
        try:
            msg = json.dumps({
                "ok": False,
                "error": "Nexus timed out after %d seconds (PID %d)" % (timeout, pid),
            })
            sys.stderr.write(msg + "\n")
            sys.stderr.flush()
        except Exception:
            pass
        os._exit(1)

    t = threading.Thread(target=_die, daemon=True)
    t.start()
