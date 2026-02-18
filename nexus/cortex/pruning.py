"""Cortex Pruning — per-command policies for automatic output reduction.

Data-driven rules that auto-reduce Nexus results based on command type.
Applied automatically in daemon/MCP mode, opt-in via --auto in CLI mode.

Each policy is a dict with optional keys:
  max_elements: int  — auto-summarize if element/node count exceeds this
  auto_diff: bool    — return diff instead of full result if same context
  preferred_format: str — suggest "compact" or "minimal" to caller
  soft_trim: dict    — head+tail truncation for text-heavy results
  never_prune: bool  — skip all pruning

Zero LLM calls. All local processing.
"""


# ---------------------------------------------------------------------------
# Policy definitions — tune these numbers freely
# ---------------------------------------------------------------------------

POLICIES = {
    # Awareness commands — can be large, benefit from auto-reduction
    "describe": {
        "max_elements": 80,
        "auto_diff": True,
        "preferred_format": "compact",
    },
    "web-ax": {
        "max_elements": 100,
        "preferred_format": "compact",
    },
    "web-describe": {
        "preferred_format": "compact",
    },
    "web-text": {
        "soft_trim": {"max_chars": 5000, "head_lines": 40, "tail_lines": 10},
    },
    "web-markdown": {
        "soft_trim": {"max_chars": 8000, "head_lines": 60, "tail_lines": 15},
    },
    "web-links": {
        "max_elements": 50,
        "preferred_format": "compact",
    },
    "windows": {
        "preferred_format": "compact",
    },
    "find": {
        "max_elements": 40,
        "preferred_format": "compact",
    },
    # Always full — never prune
    "screenshot": {"never_prune": True},
    "focused": {"never_prune": True},
    "info": {"never_prune": True},
    "ocr-region": {"never_prune": True},
    "ocr-screen": {"never_prune": True},
    # Action commands — always full (small results, context matters)
    "click": {"never_prune": True},
    "move": {"never_prune": True},
    "drag": {"never_prune": True},
    "type": {"never_prune": True},
    "key": {"never_prune": True},
    "scroll": {"never_prune": True},
    "click-element": {"never_prune": True},
    "click-mark": {"never_prune": True},
    "web-click": {"never_prune": True},
    "web-navigate": {"never_prune": True},
    "web-input": {"never_prune": True},
    "web-pdf": {"never_prune": True},
    "ps-run": {"never_prune": True},
    "com-shell": {"never_prune": True},
    "com-excel": {"never_prune": True},
    "com-word": {"never_prune": True},
    "com-outlook": {"never_prune": True},
}


def get_policy(command: str) -> dict:
    """Return the pruning policy for a command. Returns {} if no policy."""
    return POLICIES.get(command, {})


def apply_policy(command: str, result: dict, cache_kwargs: dict = None) -> dict:
    """Apply pruning policy to a command result.

    Returns the (possibly reduced) result dict.
    If a format is suggested, adds "_suggested_format" key (caller pops it).

    Applied in order:
    1. auto_diff — if same context, compute diff
    2. max_elements — auto-summarize if over threshold
    3. soft_trim — head+tail truncation for text fields
    4. preferred_format — suggest format level
    """
    policy = get_policy(command)
    if not policy or policy.get("never_prune"):
        return result

    # 1. Auto-diff: if same context detected, return diff instead of full
    if policy.get("auto_diff") and cache_kwargs is not None:
        diffed = _try_auto_diff(command, result, cache_kwargs)
        if diffed is not None:
            return diffed

    # 2. Max elements: auto-summarize if over threshold
    max_el = policy.get("max_elements")
    if max_el:
        result = _try_auto_summarize(command, result, max_el)

    # 3. Soft trim: truncate long text fields
    trim = policy.get("soft_trim")
    if trim:
        result = _try_soft_trim(result, trim)

    # 4. Preferred format: suggest to caller
    pf = policy.get("preferred_format")
    if pf:
        result["_suggested_format"] = pf

    return result


def soft_trim_text(text: str, max_chars: int, head_lines: int, tail_lines: int) -> str:
    """Head+tail truncation with omission notice in the middle."""
    if len(text) <= max_chars:
        return text

    lines = text.split("\n")
    if len(lines) <= head_lines + tail_lines:
        return text

    head = lines[:head_lines]
    tail = lines[-tail_lines:]
    omitted = len(lines) - head_lines - tail_lines

    return "\n".join(head) + "\n\n... (%d lines omitted) ...\n\n" % omitted + "\n".join(tail)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _try_auto_diff(command: str, result: dict, cache_kwargs: dict):
    """Try to return a diff if we have a cached previous result for the same context.

    Returns the diff dict, or None if no previous result or diff not applicable.
    Only works with in-memory cache (daemon mode).
    """
    try:
        from nexus.cache import cache_get_for_diff, compute_diff, cache_put

        old_result = cache_get_for_diff(command, cache_kwargs, use_file=False)
        # Always update cache with current result
        cache_put(command, cache_kwargs, result, use_file=False)

        if old_result is None:
            return None

        diff = compute_diff(old_result, result)
        # Only use diff if there are actual changes (otherwise return full)
        if diff.get("mode") == "diff":
            added = len(diff.get("added", []))
            removed = len(diff.get("removed", []))
            changed = len(diff.get("changed", []))
            if added + removed + changed > 0:
                return diff
        return None
    except Exception:
        return None


def _try_auto_summarize(command: str, result: dict, max_elements: int) -> dict:
    """Auto-summarize if element count exceeds threshold."""
    # Count elements based on command type
    element_count = 0
    if command in ("describe", "find"):
        elements = result.get("elements", [])
        element_count = len(elements) if isinstance(elements, list) else 0
    elif command in ("web-ax",):
        nodes = result.get("nodes", [])
        element_count = len(nodes) if isinstance(nodes, list) else 0
    elif command in ("web-links",):
        links = result.get("links", [])
        element_count = len(links) if isinstance(links, list) else 0

    if element_count <= max_elements:
        return result

    # Summarize based on command type
    try:
        if command in ("describe", "find"):
            from nexus.cortex.summarize import summarize_uia
            summary = summarize_uia(result)
            return {"command": command, "mode": "summary", "auto_pruned": True, **summary}
        elif command == "web-ax":
            from nexus.cortex.summarize import summarize_web
            summary = summarize_web(result)
            return {"command": command, "mode": "summary", "auto_pruned": True, **summary}
    except Exception:
        pass

    return result


def _try_soft_trim(result: dict, trim_config: dict) -> dict:
    """Apply soft-trim to text-heavy result fields."""
    max_chars = trim_config.get("max_chars", 5000)
    head_lines = trim_config.get("head_lines", 40)
    tail_lines = trim_config.get("tail_lines", 10)

    # Check common text fields
    for key in ("text", "content", "markdown"):
        text = result.get(key)
        if isinstance(text, str) and len(text) > max_chars:
            original_len = len(text)
            result = dict(result)  # shallow copy to avoid mutating cached version
            result[key] = soft_trim_text(text, max_chars, head_lines, tail_lines)
            result["_trimmed"] = {
                "field": key,
                "original_chars": original_len,
                "trimmed_to_chars": len(result[key]),
            }
            break

    return result
