"""Phase 2 mastery capture — pure score → node_state transitions (no Streamlit, no LLM).

Extracted verbatim from ``app.py`` so the same sticky-mastery logic runs from both the Streamlit UI
and the FastAPI service. Unit-tested via ``tests/test_mastery_capture.py`` (imports re-exported from
``app`` for back-compat).
"""

# Mastery thresholds (Phase 2): score → node status.
MASTERY_THRESHOLD = 80   # >= mastered
REVIEW_THRESHOLD = 50    # >= in_progress, below ⇒ needs_review


def default_node_state() -> dict:
    """Fresh node_state entry (matches the SCOUT-init shape) for newly added remedial nodes."""
    return {"status": "available", "best_score": 0, "attempts": 0, "weaknesses": [], "last_feedback": None}


def apply_score(ls: dict, node_id: str, fmt: str, result: dict) -> None:
    """Write a grade result into ``learning_session['node_state'][node_id]``.

    Pure state update (builds a new node_state entry) so it's unit-testable without a Streamlit
    context. Both coding_challenge and case_study expose 'score' (0–100). Mutates ``ls`` in place to
    mirror the original Streamlit behavior (caller persists the whole ls afterwards).
    """
    score = float(result.get("score", 0.0) or 0.0)
    old = ls["node_state"].get(node_id, {})
    best_score = max(old.get("best_score", 0), score)
    # Mastery is sticky: once best_score clears the bar the node stays mastered even after a worse
    # retry. in_progress/needs_review track the latest attempt so genuine struggle still surfaces.
    if best_score >= MASTERY_THRESHOLD:
        status = "mastered"
    elif score >= REVIEW_THRESHOLD:
        status = "in_progress"
    else:
        status = "needs_review"
    ls["node_state"][node_id] = {
        **old,
        "status": status,
        "best_score": best_score,
        "attempts": old.get("attempts", 0) + 1,
        "weaknesses": old.get("weaknesses", []),  # Phase 3 fills remediation_focus
        "last_feedback": result,
    }


def feedback_text(result: dict | None) -> str:
    """Flatten a grade result into a short text blob the Adaptation agent can read as gaps."""
    if not result:
        return ""
    parts: list[str] = []
    for f in result.get("failures", []) or []:
        parts.append(str(f))
    if result.get("feedback"):
        parts.append(str(result["feedback"]))
    for line in result.get("per_criterion", []) or []:
        parts.append(str(line))
    return "\n".join(parts)[:2000]  # cap: keep the adaptation prompt bounded
