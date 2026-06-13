"""Phase 3 — deterministic merge: apply_adaptation preserves ids, appends, dedups (no LLM)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from graph.skill_graph_adapt import apply_adaptation


def _graph():
    return {
        "summary": "roadmap",
        "nodes": [
            {"id": "loops", "label": "Loops", "description": "iteration", "level": "foundational"},
            {"id": "funcs", "label": "Functions", "description": "callables", "level": "intermediate"},
        ],
        "edges": [{"source": "loops", "target": "funcs", "relation": "prerequisite"}],
    }


def test_low_score_adds_remedial_node_and_inbound_edge():
    adaptation = {
        "new_nodes": [{"id": "loop_basics", "label": "Loop Basics", "description": "off-by-one", "level": "foundational"}],
        "new_edges": [{"source": "loop_basics", "target": "loops", "relation": "prerequisite"}],
        "remediation_focus": ["off-by-one"],
        "rationale": "remedial",
    }
    new_graph, new_ids = apply_adaptation(_graph(), adaptation)
    ids = [n["id"] for n in new_graph["nodes"]]
    assert ids == ["loops", "funcs", "loop_basics"]
    assert new_ids == ["loop_basics"]
    assert {"source": "loop_basics", "target": "loops", "relation": "prerequisite"} in new_graph["edges"]


def test_existing_id_is_never_overwritten():
    adaptation = {
        "new_nodes": [{"id": "loops", "label": "HIJACK", "description": "x", "level": "advanced"}],
        "new_edges": [],
        "remediation_focus": [],
        "rationale": "",
    }
    new_graph, new_ids = apply_adaptation(_graph(), adaptation)
    assert new_ids == []
    loops = next(n for n in new_graph["nodes"] if n["id"] == "loops")
    assert loops["label"] == "Loops"  # original preserved, not hijacked


def test_duplicate_edge_is_not_appended():
    adaptation = {
        "new_nodes": [],
        "new_edges": [{"source": "loops", "target": "funcs", "relation": "prerequisite"}],
        "remediation_focus": [],
        "rationale": "",
    }
    new_graph, _ = apply_adaptation(_graph(), adaptation)
    assert len(new_graph["edges"]) == 1


def test_high_score_adds_unlock_edge():
    adaptation = {
        "new_nodes": [],
        "new_edges": [{"source": "loops", "target": "funcs", "relation": "unlock"}],
        "remediation_focus": [],
        "rationale": "mastered",
    }
    new_graph, new_ids = apply_adaptation(_graph(), adaptation)
    assert new_ids == []
    assert any(e.get("relation") == "unlock" for e in new_graph["edges"])


def test_edge_referencing_unknown_node_is_dropped():
    adaptation = {
        "new_nodes": [],
        "new_edges": [{"source": "ghost", "target": "loops", "relation": "prerequisite"}],
        "remediation_focus": [],
        "rationale": "",
    }
    new_graph, _ = apply_adaptation(_graph(), adaptation)
    assert len(new_graph["edges"]) == 1  # orphan edge skipped


def test_input_graph_is_not_mutated():
    g = _graph()
    adaptation = {
        "new_nodes": [{"id": "x", "label": "X", "description": "x", "level": "foundational"}],
        "new_edges": [{"source": "x", "target": "loops", "relation": "prerequisite"}],
        "remediation_focus": [],
        "rationale": "",
    }
    apply_adaptation(g, adaptation)
    assert len(g["nodes"]) == 2  # original untouched
    assert len(g["edges"]) == 1


def test_accepts_pydantic_adaptation():
    from agents.adaptation.adaptation_schema import GraphAdaptation

    adaptation = GraphAdaptation(
        new_nodes=[{"id": "n3", "label": "N3", "description": "d", "level": "foundational"}],
        new_edges=[{"source": "n3", "target": "loops", "relation": "prerequisite"}],
        remediation_focus=["gap"],
        rationale="r",
    )
    new_graph, new_ids = apply_adaptation(_graph(), adaptation)
    assert new_ids == ["n3"]
