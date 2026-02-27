"""Intent router — tries direct automation before GUI fallback.

Sits between _normalize_action() and the verb dispatcher in resolve.py.
If a recipe matches and succeeds, returns the result immediately.
If no match or recipe fails, returns None so GUI takes over.
"""

from nexus.via.recipe import match_recipe, execute_recipe


def route(action, pid=None):
    """Try direct automation for this action.

    Returns:
        dict with result if a recipe handled it (includes "via" key).
        None if no recipe matched or recipe failed (fall through to GUI).
    """
    rcp, match = match_recipe(action, pid=pid)
    if rcp:
        result = execute_recipe(rcp, match, pid=pid)
        if result and result.get("ok"):
            result["via"] = f"recipe ({rcp.name})"
            return result
        # Recipe failed — fall through to GUI silently

    return None
