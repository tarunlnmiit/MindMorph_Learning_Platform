"""Deterministic Skill Dependency Graph -> Mermaid renderer.

No LLM call: the Consensus agent emits structured JSON; this turns it into a
Mermaid flowchart string for the UI. Keeping it deterministic guarantees the
visual always matches the JSON artifact.
"""
import re
from typing import Any

_LEVEL_CLASS = {"foundational": "foundational", "intermediate": "intermediate", "advanced": "advanced"}


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


def skill_graph_to_mermaid(graph: Any) -> str:
    """Render a SkillGraph (pydantic model or dict) as a Mermaid flowchart string."""
    data = _as_dict(graph)
    nodes = data.get("nodes") or []
    edges = data.get("edges") or []
    if not nodes:
        return ""

    lines = ["flowchart TD"]
    levels_used = set()

    for n in nodes:
        nid = _safe_id(n.get("id"))
        if not nid:
            continue
        lines.append(f'    {nid}["{_escape_label(n.get("label") or n.get("id"))}"]')

    for e in edges:
        s = _safe_id(e.get("source"))
        t = _safe_id(e.get("target"))
        if s and t:
            lines.append(f"    {s} --> {t}")

    # Style nodes by difficulty level.
    lines.append("    classDef foundational fill:#dbeafe,stroke:#2563eb,color:#1e3a8a;")
    lines.append("    classDef intermediate fill:#fef9c3,stroke:#ca8a04,color:#713f12;")
    lines.append("    classDef advanced fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;")
    for n in nodes:
        nid = _safe_id(n.get("id"))
        cls = _LEVEL_CLASS.get((n.get("level") or "").lower())
        if nid and cls:
            lines.append(f"    class {nid} {cls};")
            levels_used.add(cls)

    return "\n".join(lines)
