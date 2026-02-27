"""Via — learned routes for deterministic navigation.

The "legs" of Nexus. Record user actions once, replay them at machine speed
with zero LLM tokens. Each route stores AX locators + relative coordinates
for position-independent replay.

Usage:
    do("via record gmail-login")  → start recording
    (user performs actions)
    do("via stop")                → stop and save route
    do("via replay gmail-login")  → replay at machine speed
    do("via list")                → list saved routes
    do("via delete gmail-login")  → remove a route
"""

from nexus.via.recorder import (  # noqa: F401
    start_recording,
    stop_recording,
    is_recording,
    list_recordings,
    get_recording,
    delete_recording,
)
from nexus.via.player import replay  # noqa: F401
from nexus.via.tap import shutdown  # noqa: F401
from nexus.via.recipe import list_recipes  # noqa: F401
from nexus.via.router import route  # noqa: F401
