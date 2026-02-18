"""Nexus Batch — execute multiple commands in sequence, return final result.

Reduces context round-trips by chaining commands:
  nexus batch "describe --focus buttons; find Save; click-element Save"

Features:
  - Semicolon-separated commands
  - Variable interpolation: $name, $x, $y from previous result
  - Only final result returned (or --verbose for all)
  - Fail-fast by default
  - Post-processing flags (--summary, --diff) work inside batch steps
"""

import re
import shlex


def parse_batch(batch_str: str) -> list[str]:
    """Parse a semicolon-separated batch string into individual command strings."""
    commands = []
    for part in batch_str.split(";"):
        cmd = part.strip()
        if cmd:
            commands.append(cmd)
    return commands


def interpolate(cmd_str: str, prev_result: dict) -> str:
    """Replace $variable references with values from the previous result.

    Supported:
      $name     — result["name"] or first match name
      $x, $y    — coordinates (from "at" or first match bounds)
      $url      — result["url"]
      $title    — result["title"]
      $count    — result["count"]
      $clicked  — result["clicked"]
      ${key}    — any top-level key from prev_result
    """
    if "$" not in cmd_str:
        return cmd_str

    # Build a flat lookup from the previous result
    lookup = {}

    # Direct top-level keys
    for k, v in prev_result.items():
        if isinstance(v, (str, int, float)):
            lookup[k] = str(v)

    # Extract name from various result shapes
    if "clicked" in prev_result:
        lookup.setdefault("name", prev_result["clicked"])
    if "matches" in prev_result and prev_result["matches"]:
        first = prev_result["matches"][0]
        lookup.setdefault("name", first.get("name", ""))
        bounds = first.get("bounds", {})
        lookup.setdefault("x", str(bounds.get("center_x", bounds.get("x", 0))))
        lookup.setdefault("y", str(bounds.get("center_y", bounds.get("y", 0))))
    if "elements" in prev_result and prev_result["elements"]:
        first = prev_result["elements"][0]
        lookup.setdefault("name", first.get("name", ""))
        bounds = first.get("bounds", {})
        lookup.setdefault("x", str(bounds.get("center_x", bounds.get("x", 0))))
        lookup.setdefault("y", str(bounds.get("center_y", bounds.get("y", 0))))
    if "at" in prev_result:
        lookup.setdefault("x", str(prev_result["at"].get("x", 0)))
        lookup.setdefault("y", str(prev_result["at"].get("y", 0)))
    if "nodes" in prev_result and prev_result["nodes"]:
        first = prev_result["nodes"][0]
        lookup.setdefault("name", first.get("name", ""))

    # Replace ${key} and $key patterns
    def _replace(m):
        key = m.group(1) or m.group(2)
        return lookup.get(key, m.group(0))

    # ${key} pattern first, then $key
    result = re.sub(r'\$\{(\w+)\}', _replace, cmd_str)
    result = re.sub(r'\$(\w+)', _replace, result)
    return result


def _apply_post_processing(cmd_name: str, result: dict, flags: dict) -> dict:
    """Apply --summary and --diff post-processing to a step result.

    These flags are handled in run.py for single-shot mode, but batch steps
    need them applied inline so intermediate results can feed the next step.
    """
    if flags.get("summary") and cmd_name == "describe":
        from nexus.cortex.summarize import summarize_uia
        summary = summarize_uia(result)
        return {"command": "describe", "mode": "summary", **summary}
    if flags.get("summary") and cmd_name == "web-ax":
        from nexus.cortex.summarize import summarize_web
        summary = summarize_web(result)
        return {"command": "web-ax", "mode": "summary", **summary}

    if flags.get("diff") and cmd_name in ("describe", "web-ax"):
        from nexus.cache import cache_get_for_diff, compute_diff, cache_put
        cache_kwargs = {k: v for k, v in flags.get("cmd_kwargs", {}).items() if v is not None}
        old_result = cache_get_for_diff(cmd_name, cache_kwargs, use_file=True)
        cache_put(cmd_name, cache_kwargs, result, use_file=True)
        if old_result:
            return compute_diff(old_result, result)

    return result


def execute_batch(batch_str: str, commands: dict, verbose: bool = False,
                  continue_on_error: bool = False) -> dict:
    """Execute a batch of commands sequentially.

    Args:
        batch_str: Semicolon-separated command string.
        commands: The command dispatch table {name: (func, extractor)}.
        verbose: If True, return all intermediate results.
        continue_on_error: If True, continue executing after a failure.

    Returns:
        Final result (or all results if verbose), plus batch metadata.
    """
    steps = parse_batch(batch_str)
    if not steps:
        return {"command": "batch", "ok": False, "error": "No commands in batch"}

    results = []
    prev_result = {}

    for i, step_str in enumerate(steps):
        # Interpolate variables from previous result
        step_str = interpolate(step_str, prev_result)

        # Parse the step into command name + args
        try:
            parts = shlex.split(step_str)
        except ValueError as e:
            err = {"command": "batch", "ok": False, "step": i,
                   "error": "Parse error in step %d: %s" % (i, str(e)),
                   "raw": step_str}
            if continue_on_error:
                results.append(err)
                continue
            return err

        if not parts:
            continue

        cmd_name = parts[0]

        # Strip leading "nexus" or "python -m nexus" if present
        if cmd_name in ("nexus", "python"):
            parts = parts[1:]
            if parts and parts[0] in ("-m", "nexus"):
                parts = parts[1:]
            if not parts:
                continue
            cmd_name = parts[0]

        if cmd_name not in commands:
            err = {"command": "batch", "ok": False, "step": i,
                   "error": "Unknown command: '%s'" % cmd_name}
            if continue_on_error:
                results.append(err)
                continue
            return err

        func, extract = commands[cmd_name]

        # Build kwargs dict from remaining args
        raw_kwargs = _parse_step_args(cmd_name, parts[1:], extract)

        # Extract post-processing flags before passing to extractor
        post_flags = {
            "summary": raw_kwargs.pop("summary", False),
            "diff": raw_kwargs.pop("diff", False),
        }

        # Use the daemon extractor to get proper kwargs
        try:
            kwargs = extract(raw_kwargs)
        except Exception:
            kwargs = raw_kwargs

        # Store clean kwargs for diff cache key
        post_flags["cmd_kwargs"] = kwargs

        try:
            result = func(**kwargs)
            # Apply post-processing (--summary, --diff) if requested
            result = _apply_post_processing(cmd_name, result, post_flags)
            prev_result = result
            results.append(result)
        except Exception as e:
            err = {"command": cmd_name, "ok": False, "step": i,
                   "error": str(e)[:300]}
            if continue_on_error:
                results.append(err)
                prev_result = err
                continue
            return err

    if verbose:
        return {
            "command": "batch",
            "ok": True,
            "steps": len(results),
            "results": results,
        }
    else:
        # Return only the final result + batch metadata
        final = results[-1] if results else {}
        final["_batch"] = {"steps_total": len(steps), "steps_completed": len(results)}
        return final


def _parse_step_args(cmd_name: str, args: list[str], extract) -> dict:
    """Parse step arguments into kwargs for the command function.

    Uses a simple approach: positional args go to known positional params,
    --flag args are parsed as key=value or boolean flags.
    """
    # Known positional params per command
    _POSITIONALS = {
        "find": ["query"],
        "web-find": ["query"],
        "click-element": ["name"],
        "web-click": ["text"],
        "web-navigate": ["url"],
        "web-input": ["selector", "value"],
        "web-measure": ["selectors"],
        "ps-run": ["script"],
        "click": ["x", "y"],
        "move": ["x", "y"],
        "type": ["text"],
        "key": ["keyname"],
        "scroll": ["amount"],
        "web-research": ["query"],
        "ocr-region": ["x", "y", "w", "h"],
    }

    positional_names = _POSITIONALS.get(cmd_name, [])

    # Split into positional and flag args
    kwargs = {}
    positional_idx = 0
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("--"):
            key = arg[2:].replace("-", "_")
            # Check if next arg is a value or if this is a boolean flag
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                val = args[i + 1]
                # Try to parse as int/float/bool
                if val.lower() in ("true", "false"):
                    kwargs[key] = val.lower() == "true"
                else:
                    try:
                        kwargs[key] = int(val)
                    except ValueError:
                        try:
                            kwargs[key] = float(val)
                        except ValueError:
                            kwargs[key] = val
                i += 2
            else:
                kwargs[key] = True
                i += 1
        else:
            # Positional arg
            if positional_idx < len(positional_names):
                name = positional_names[positional_idx]
                try:
                    kwargs[name] = int(arg)
                except ValueError:
                    kwargs[name] = arg
                positional_idx += 1
            i += 1

    return kwargs
