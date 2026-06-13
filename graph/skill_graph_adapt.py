"""Phase 3 — deterministic application of a GraphAdaptation to a SkillGraph (no LLM).

The Adaptation agent proposes additive changes; this module applies them under a hard invariant:
adaptation may only ADD new nodes/edges — never rename or delete an existing node id (mastery state
and cached lessons key off node_id). The merge is immutable: it builds a brand-new graph dict and
never mutates the input.
"""
from typing import Any, List, Tuple


def _as_dict(obj: Any) -> dict:
    """Normalize a pydantic model or dict to a plain dict."""
    if obj is None:
        return {}
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if isinstance(obj, dict):
        return obj
    return {}


def _edge_key(edge: dict) -> tuple:
    return (edge.get("source"), edge.get("target"), edge.get("relation") or "prerequisite")


def apply_adaptation(skill_graph: Any, adaptation: Any) -> Tuple[dict, List[str]]:
    """Merge an adaptation into a skill graph, returning (new_graph, new_node_ids).

    - Immutable: the input graph is never mutated; a new dict with new node/edge lists is returned.
    - Additive only: existing node ids are preserved; a proposed new node whose id already exists is
      dropped (the invariant — never overwrite an existing node).
    - Dedup: edges already present (same source/target/relation) are not duplicated.

    new_node_ids is the list of ids that were actually added, so the caller can seed node_state.
    """
    graph = _as_dict(skill_graph)
    adapt = _as_dict(adaptation)

    existing_nodes = [dict(n) for n in (graph.get("nodes") or [])]
    existing_ids = {n.get("id") for n in existing_nodes}

    merged_nodes = list(existing_nodes)
    new_node_ids: List[str] = []
    for proposed in adapt.get("new_nodes") or []:
        node = _as_dict(proposed)
        nid = node.get("id")
        # Invariant: only ADD — never overwrite an existing id, and never add the same new id twice.
        if not nid or nid in existing_ids:
            continue
        existing_ids.add(nid)
        merged_nodes.append(node)
        new_node_ids.append(nid)

    existing_edges = [dict(e) for e in (graph.get("edges") or [])]
    seen_edges = {_edge_key(e) for e in existing_edges}

    merged_edges = list(existing_edges)
    for proposed in adapt.get("new_edges") or []:
        edge = _as_dict(proposed)
        key = _edge_key(edge)
        # Skip duplicates and edges that reference a node id present in neither the old graph
        # nor the just-added nodes (a hallucinated endpoint would orphan the edge).
        if key in seen_edges:
            continue
        if edge.get("source") not in existing_ids or edge.get("target") not in existing_ids:
            continue
        seen_edges.add(key)
        merged_edges.append(edge)

    new_graph = {**graph, "nodes": merged_nodes, "edges": merged_edges}
    return new_graph, new_node_ids
