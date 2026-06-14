"""Prerequisite-gated completion — pure skill-graph derivations (no Streamlit, no LLM).

Per-node mastery (``best_score >= 80``, sticky) is the underlying truth. "Complete" is derived: a node
counts as complete only when it AND all its prerequisites (transitively) are mastered. A node that
passed its own exercise but still has an incomplete prerequisite renders as 'blocked' (🔒), not
'mastered' (✅), and is excluded from the progress count. Extracted from ``app.py``; unit-tested via
``tests/test_completion_gating.py``.
"""

# Picker ordering: foundational -> intermediate -> advanced. Phase 3 appends remedial nodes to the
# end of the nodes list; sorting by level rank (stable within a level) realigns the picker with the
# graph's reading order.
_LEVEL_RANK = {"foundational": 0, "intermediate": 1, "advanced": 2}


def node_label_map(skill_graph: dict) -> dict:
    """Map node_id -> label for the skill picker (ids are unique; labels may repeat)."""
    return {n["id"]: n.get("label", n["id"]) for n in skill_graph.get("nodes", [])}


def ordered_node_ids(skill_graph: dict) -> list:
    nodes = skill_graph.get("nodes", [])
    return [
        n["id"]
        for n in sorted(nodes, key=lambda n: _LEVEL_RANK.get((n.get("level") or "").lower(), 1))
    ]


def prereqs_by_node(skill_graph: dict) -> dict:
    """Map node_id -> set of its prerequisite ids. Edge convention (SkillEdge): source = prerequisite,
    target = the skill that depends on it. So prereqs of X = sources of edges whose target is X."""
    prereqs: dict = {n["id"]: set() for n in skill_graph.get("nodes", [])}
    for e in skill_graph.get("edges", []) or []:
        src, tgt = e.get("source"), e.get("target")
        if tgt in prereqs and src is not None:
            prereqs[tgt].add(src)
    return prereqs


def complete_node_ids(skill_graph: dict, node_state: dict) -> set:
    """Set of node ids that are fully complete: mastered AND every prerequisite complete (recursive).

    Memoized with a cycle guard — a node currently being resolved is treated as not-complete, so a
    cyclic graph returns instead of recursing forever (the graph is meant to be acyclic).
    """
    prereqs = prereqs_by_node(skill_graph)

    def _is_mastered(nid: str) -> bool:
        return node_state.get(nid, {}).get("status") == "mastered"

    memo: dict = {}
    visiting: set = set()

    def _complete(nid: str) -> bool:
        if nid in memo:
            return memo[nid]
        if nid in visiting:  # cycle: don't recurse, count as not-complete
            return False
        if not _is_mastered(nid):
            memo[nid] = False
            return False
        visiting.add(nid)
        result = all(_complete(p) for p in prereqs.get(nid, set()))
        visiting.discard(nid)
        memo[nid] = result
        return result

    return {nid for nid in prereqs if _complete(nid)}


def locked_node_ids(skill_graph: dict, node_state: dict) -> set:
    """Set of node ids that are LOCKED: at least one direct prerequisite is not complete.

    A learner may not open a locked node's lesson. Transitivity is automatic — completion is
    transitive, so a node downstream of an unmastered node has an incomplete prerequisite and is
    locked too. Root nodes (no prerequisites) and complete nodes are never locked.
    """
    complete = complete_node_ids(skill_graph, node_state)
    prereqs = prereqs_by_node(skill_graph)
    return {nid for nid, ps in prereqs.items() if any(p not in complete for p in ps)}


def incomplete_prereq_labels(skill_graph: dict, node_state: dict, node_id: str) -> list:
    """Labels of a node's direct prerequisites that are not yet complete (for the lock message)."""
    complete = complete_node_ids(skill_graph, node_state)
    label_by_id = node_label_map(skill_graph)
    prereqs = prereqs_by_node(skill_graph).get(node_id, set())
    return [label_by_id.get(p, p) for p in prereqs if p not in complete]


def display_status(skill_graph: dict, node_state: dict) -> dict:
    """node_id -> status handed to the renderer. Complete -> 'mastered' (✅); any node with an
    incomplete prerequisite (locked) -> 'blocked' (🔒); otherwise the underlying status (unchanged).
    The mastered-but-prereq-pending case is a subset of locked, so its 🔒 behavior is preserved."""
    complete = complete_node_ids(skill_graph, node_state)
    locked = locked_node_ids(skill_graph, node_state)
    out: dict = {}
    for nid, s in node_state.items():
        if nid in complete:
            out[nid] = "mastered"
        elif nid in locked:
            out[nid] = "blocked"
        else:
            out[nid] = s.get("status")
    return out
