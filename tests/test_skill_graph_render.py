"""Deterministic skill-graph -> Mermaid rendering."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from graph.skill_graph_render import skill_graph_to_mermaid


def test_render_sanitizes_ids_escapes_labels_and_styles_levels():
    graph = {
        "nodes": [
            {"id": "a b", "label": 'A "x"', "level": "foundational"},
            {"id": "c", "label": "C", "level": "advanced"},
        ],
        "edges": [{"source": "a b", "target": "c"}],
    }
    m = skill_graph_to_mermaid(graph)

    assert m.startswith("flowchart TD")
    assert "a_b[\"A 'x'\"]" in m       # non-alnum id sanitized, quotes escaped
    assert "a_b --> c" in m            # edge uses sanitized ids
    assert "class a_b foundational;" in m
    assert "class c advanced;" in m


def test_render_empty_graph_returns_empty_string():
    assert skill_graph_to_mermaid({"nodes": [], "edges": []}) == ""
    assert skill_graph_to_mermaid(None) == ""
