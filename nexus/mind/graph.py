"""Navigation graph — passive state transition recording (Phase 8).

Every successful do() action that changes the UI state (different layout
hash before/after) is recorded as an edge in a directed graph. Nodes are
layout hashes (12-char fingerprints of element roles+labels). Edges are
action strings that caused the transition.

Over time, the graph learns the topology of every app's UI:
  - System Settings: "General" → click "About" → "About" pane
  - Safari: "Gmail inbox" → click "Compose" → "New message"

The graph enables pathfinding: given the current state hash and a target
state hash, BFS finds the shortest action sequence to get there.

All recording is passive — the graph_record hook fires automatically
after every do() action. No user interaction needed.
"""

from collections import deque

from nexus.mind import db


def record_transition(before_hash, after_hash, action, app, ok, elapsed):
    """Record a state transition in the navigation graph.

    Creates/updates nodes and the connecting edge.
    Skips if before_hash == after_hash (no state change).
    """
    if not before_hash or not after_hash:
        return
    if before_hash == after_hash:
        return

    # Upsert both nodes
    db.node_upsert(before_hash, app)
    db.node_upsert(after_hash, app)

    # Upsert edge
    db.edge_upsert(before_hash, after_hash, action, ok, elapsed)


def find_path(from_hash, to_hash):
    """Find shortest path between two layout states.

    Returns list of {"action": str, "from": hash, "to": hash} or None.
    Uses BFS (unweighted — prefers fewer steps).
    """
    if from_hash == to_hash:
        return []

    edges = db.all_edges()
    if not edges:
        return None

    # Build adjacency list
    adj = {}
    for e in edges:
        adj.setdefault(e["from_hash"], []).append(e)

    # BFS
    queue = deque([(from_hash, [])])
    visited = {from_hash}

    while queue:
        current, path = queue.popleft()
        for edge in adj.get(current, []):
            next_hash = edge["to_hash"]
            step = {"action": edge["action"], "from": current, "to": next_hash}
            if next_hash == to_hash:
                return path + [step]
            if next_hash not in visited:
                visited.add(next_hash)
                queue.append((next_hash, path + [step]))

    return None  # No path found


def suggest_action(current_hash, target_hash):
    """Suggest the next do() action to get from current to target state.

    Returns the action string for the first step, or None if no path.
    """
    path = find_path(current_hash, target_hash)
    if path:
        return path[0]["action"]
    return None


def graph_stats():
    """Return summary of the navigation graph."""
    conn = db._get_conn()
    nodes = conn.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0]
    edges = conn.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]
    apps = conn.execute("SELECT DISTINCT app FROM graph_nodes").fetchall()
    return {
        "nodes": nodes,
        "edges": edges,
        "apps": [r["app"] for r in apps],
    }
