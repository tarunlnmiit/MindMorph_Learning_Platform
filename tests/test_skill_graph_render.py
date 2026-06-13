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


_STATUS_GRAPH = {
    "nodes": [
        {"id": "a", "label": "A", "level": "foundational"},
        {"id": "b", "label": "B", "level": "advanced"},
        {"id": "c", "label": "C", "level": "intermediate"},
    ],
    "edges": [{"source": "a", "target": "b"}],
}


def test_node_status_adds_glyphs_and_status_classes():
    status = {"a": "mastered", "b": "needs_review", "c": "available"}
    m = skill_graph_to_mermaid(_STATUS_GRAPH, status)

    assert 'a["✅ A"]' in m               # mastered glyph on label
    assert 'b["🔁 B"]' in m               # needs_review glyph
    assert 'c["C"]' in m                  # available ⇒ no glyph
    assert "classDef mastered fill:#dcfce7" in m
    assert "classDef needs_review" in m
    assert "class a mastered;" in m       # status class applied (after level ⇒ overrides)
    assert "class b needs_review;" in m
    assert "class c available;" not in m  # available has no status class


def test_node_status_absent_is_backcompat():
    base = skill_graph_to_mermaid(_STATUS_GRAPH)
    assert base == skill_graph_to_mermaid(_STATUS_GRAPH, None)
    assert base == skill_graph_to_mermaid(_STATUS_GRAPH, {})
    assert "classDef mastered" not in base  # no status lines emitted without statuses


def test_blocked_status_renders_lock_glyph_and_class():
    status = {"a": "blocked", "b": "mastered"}
    m = skill_graph_to_mermaid(_STATUS_GRAPH, status)
    assert 'a["🔒 A"]' in m                 # blocked => lock glyph, not the ✅
    assert "classDef blocked" in m
    assert "class a blocked;" in m
    assert 'b["✅ B"]' in m                  # genuinely-complete node still ✅
