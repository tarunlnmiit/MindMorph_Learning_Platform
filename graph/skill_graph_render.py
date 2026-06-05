"""Deterministic Skill Dependency Graph -> Mermaid renderer.

No LLM call: the Consensus agent emits structured JSON; this turns it into a
Mermaid flowchart string for the UI. Keeping it deterministic guarantees the
visual always matches the JSON artifact.
"""
import re
from typing import Any

_LEVEL_CLASS = {"foundational": "foundational", "intermediate": "intermediate", "advanced": "advanced"}

# Mastery status overlay (Phase 2): glyph appended to the label + a status class that
# overrides the level color. Only non-"available" statuses are drawn.
_STATUS_GLYPH = {"mastered": "✅", "needs_review": "🔁", "in_progress": "▶"}
_STATUS_CLASS = {"mastered": "mastered", "needs_review": "needs_review", "in_progress": "in_progress"}


def _safe_id(raw: Any) -> str:
    s = re.sub(r"[^0-9a-zA-Z_]", "_", str(raw or "")).strip("_")
    if not s:
        return ""
    if s[0].isdigit():
        s = "n_" + s
    return s


def _escape_label(raw: Any) -> str:
    return str(raw or "").replace('"', "'").replace("\n", " ").strip()


def _as_dict(graph: Any) -> dict:
    if graph is None:
        return {}
    if hasattr(graph, "model_dump"):
        return graph.model_dump()
    if hasattr(graph, "dict"):
        return graph.dict()
    if isinstance(graph, dict):
        return graph
    return {}


def skill_graph_to_mermaid(graph: Any, node_status: dict | None = None) -> str:
    """Render a SkillGraph (pydantic model or dict) as a Mermaid flowchart string.

    node_status: optional dict[node_id -> status] (Phase 2 mastery overlay). Statuses
    'mastered' / 'needs_review' / 'in_progress' append a glyph to the label and a status
    class that overrides the level color. None/empty ⇒ byte-identical to the level-only output.
    """
    data = _as_dict(graph)
    nodes = data.get("nodes") or []
    edges = data.get("edges") or []
    if not nodes:
        return ""

    status_by_id = node_status or {}
    lines = ["flowchart TD"]
    levels_used = set()

    for n in nodes:
        nid = _safe_id(n.get("id"))
        if not nid:
            continue
        label = _escape_label(n.get("label") or n.get("id"))
        glyph = _STATUS_GLYPH.get(status_by_id.get(n.get("id")))
        if glyph:
            label = f"{glyph} {label}"
        lines.append(f'    {nid}["{label}"]')

    for e in edges:
        s = _safe_id(e.get("source"))
        t = _safe_id(e.get("target"))
        if s and t:
            lines.append(f"    {s} --> {t}")

    # Mastery status overlay (Phase 2): a status node gets ONLY its status class (the level class
    # is skipped for it) so the status color always applies without relying on mermaid class-ordering.
    status_classes = [
        (nid, scls)
        for n in nodes
        if (nid := _safe_id(n.get("id")))
        and (scls := _STATUS_CLASS.get(status_by_id.get(n.get("id"))))
    ]
    status_node_ids = {nid for nid, _ in status_classes}

    # Style nodes by difficulty level (skip nodes carrying a status overlay).
    lines.append("    classDef foundational fill:#dbeafe,stroke:#2563eb,color:#1e3a8a;")
    lines.append("    classDef intermediate fill:#fef9c3,stroke:#ca8a04,color:#713f12;")
    lines.append("    classDef advanced fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;")
    for n in nodes:
        nid = _safe_id(n.get("id"))
        cls = _LEVEL_CLASS.get((n.get("level") or "").lower())
        if nid and cls and nid not in status_node_ids:
            lines.append(f"    class {nid} {cls};")
            levels_used.add(cls)

    # Status classDef + class lines: emitted only when a status is present, so the level-only
    # output stays byte-identical (back-compat).
    if status_classes:
        lines.append("    classDef mastered fill:#dcfce7,stroke:#16a34a,color:#14532d;")
        lines.append("    classDef needs_review fill:#fff,stroke:#dc2626,stroke-width:3px,color:#7f1d1d;")
        lines.append("    classDef in_progress fill:#fef3c7,stroke:#d97706,color:#78350f;")
        for nid, scls in status_classes:
            lines.append(f"    class {nid} {scls};")

    return "\n".join(lines)
