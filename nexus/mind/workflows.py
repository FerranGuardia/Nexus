"""Workflow recording and replay — Phase 8.

Record a sequence of do() actions, save as a replayable workflow.
Workflows are stored in SQLite via db.py.

Usage:
    do("record start Send Gmail")   → starts recording
    do("click Compose")             → recorded as step 1
    do("type hello")                → recorded as step 2
    do("record stop")               → saves workflow "send-gmail"
    do("replay send-gmail")         → replays all steps
    do("list workflows")            → shows saved workflows
    do("delete workflow send-gmail") → removes it
"""

import re
import time

from nexus.mind import db

# ---------------------------------------------------------------------------
# Recording state (in-memory, one active recording at a time)
# ---------------------------------------------------------------------------

_recording = None  # {"id": str, "name": str, "app": str, "steps": []}


def _slugify(name):
    """Convert 'Send Gmail Email' to 'send-gmail-email'."""
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower().strip()).strip('-')
    return slug or "unnamed"


def _unique_slug(base):
    """Ensure slug doesn't collide with existing workflow IDs."""
    slug = base
    n = 2
    while db.workflow_get(slug) is not None:
        slug = f"{base}-{n}"
        n += 1
    return slug


# ---------------------------------------------------------------------------
# Recording API
# ---------------------------------------------------------------------------

def start_recording(name, app=None):
    """Start recording a new workflow.

    Returns {"ok": True, "id": slug, "name": name}.
    """
    global _recording
    if _recording is not None:
        return {
            "ok": False,
            "error": f'Already recording workflow "{_recording["id"]}". '
                     f'Use do("record stop") first.',
        }

    slug = _unique_slug(_slugify(name))
    db.workflow_create(slug, name, app)
    _recording = {"id": slug, "name": name, "app": app, "steps": []}
    return {"ok": True, "action": "record_start", "id": slug, "name": name}


def stop_recording():
    """Stop recording and flush steps to database.

    Returns {"ok": True, "id": ..., "steps": count}.
    """
    global _recording
    if _recording is None:
        return {"ok": False, "error": "Not currently recording. Use do(\"record start <name>\") first."}

    wf_id = _recording["id"]
    steps = _recording["steps"]

    # Flush steps to DB
    for i, step in enumerate(steps):
        db.step_insert(
            workflow_id=wf_id,
            step_num=i + 1,
            action=step["action"],
            expected_hash=step.get("expected_hash"),
        )

    result = {"ok": True, "action": "record_stop", "id": wf_id, "steps": len(steps)}
    _recording = None
    return result


def is_recording():
    """Check if a recording is active."""
    return _recording is not None


def record_step(action, layout_hash=None):
    """Record a single step during active recording.

    Called by the workflow hook after each successful do() action.
    Steps accumulate in memory and are flushed on stop_recording().
    """
    if _recording is None:
        return
    _recording["steps"].append({
        "action": action,
        "expected_hash": layout_hash,
    })


# ---------------------------------------------------------------------------
# Storage API
# ---------------------------------------------------------------------------

def list_workflows():
    """List all saved workflows."""
    return db.workflow_list()


def get_workflow(workflow_id):
    """Get workflow details including steps."""
    wf = db.workflow_get(workflow_id)
    if wf is None:
        return None
    wf["steps"] = db.steps_for_workflow(workflow_id)
    return wf


def delete_workflow(workflow_id):
    """Delete a workflow and its steps."""
    return db.workflow_delete(workflow_id)


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------

def replay_workflow(workflow_id, pid=None):
    """Replay a saved workflow by executing each step in sequence.

    Returns a result dict similar to action chains.
    """
    from nexus.act.resolve import do

    wf = get_workflow(workflow_id)
    if not wf:
        return {"ok": False, "error": f'Workflow "{workflow_id}" not found'}

    steps = wf.get("steps", [])
    if not steps:
        return {"ok": False, "error": f'Workflow "{workflow_id}" has no steps'}

    results = []

    for i, step in enumerate(steps):
        result = do(step["action"], pid=pid)
        step_ok = result.get("ok", False)
        step_summary = {
            "step": i + 1,
            "action": step["action"],
            "ok": step_ok,
        }

        if not step_ok:
            step_summary["error"] = result.get("error", "unknown")
            results.append(step_summary)
            db.workflow_update_stats(workflow_id, ok=False)
            return {
                "ok": False, "action": "replay",
                "workflow": workflow_id,
                "error": f'Step {i + 1} failed: {step["action"]}',
                "completed": i, "total": len(steps),
                "steps": results,
            }

        results.append(step_summary)
        # Brief pause between steps for UI to settle
        if i < len(steps) - 1:
            time.sleep(0.15)

    db.workflow_update_stats(workflow_id, ok=True)
    return {
        "ok": True, "action": "replay",
        "workflow": workflow_id,
        "completed": len(steps), "total": len(steps),
        "steps": results,
    }
