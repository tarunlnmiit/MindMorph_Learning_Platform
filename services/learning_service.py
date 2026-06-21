"""Streamlit-free orchestration of the adaptive learning loop.

Wraps the existing LangGraph flows (orchestration + lesson compose) and the grade → mastery → adapt
chain so both the Streamlit UI and the FastAPI service drive identical logic over a plain
``learning_session`` dict. LLM-backed agents/graphs are built once per process (lazy singletons).

The async LangGraph ``ainvoke`` calls are wrapped in synchronous helpers (fresh event loop per call,
mirroring the original ``app.py``) so callers — sync FastAPI routes or Streamlit — need no async glue.
"""
import asyncio
import json
import logging
from typing import Optional

from services.completion import incomplete_prereq_labels, locked_node_ids, prereqs_by_node
from services.mastery import apply_score, default_node_state, feedback_text

logger = logging.getLogger(__name__)

# --- Lazy per-process graph/agent singletons --------------------------------------------------
_orchestration_graph = None
_lesson_graph = None
_adaptation_agent = None
_assessment_agent = None
_tutor_agent = None


def _run_async(coro):
    """Run an async coroutine to completion on a fresh event loop (matches the original app.py)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _get_orchestration_graph():
    global _orchestration_graph
    if _orchestration_graph is None:
        from agents.orchestrator.orchestrator_agent import OrchestratorAgent
        from agents.scout.scout_agent import ScoutAgent
        from agents.market.market_agent import MarketAnalysisAgent
        from agents.practical.practical_agent import PracticalAgent
        from agents.academic.academic_agent import AcademicAgent
        from graph.learning_plan_graph import build_graph

        logger.info("service: building orchestration graph (one-time)")
        _orchestration_graph = build_graph(
            orchestrator=OrchestratorAgent(push_to_langsmith=False),
            scout=ScoutAgent(push_to_langsmith=False, output_variant="Query"),
            academic=AcademicAgent(push_to_langsmith=False),
            market=MarketAnalysisAgent(),
            practical=PracticalAgent(push_to_langsmith=False),
        )
    return _orchestration_graph


def _get_lesson_graph():
    global _lesson_graph
    if _lesson_graph is None:
        from graph.lesson_graph import build_lesson_graph

        logger.info("service: building lesson graph (one-time)")
        _lesson_graph = build_lesson_graph()
    return _lesson_graph


def _get_adaptation_agent():
    global _adaptation_agent
    if _adaptation_agent is None:
        from agents.adaptation.adaptation_agent import AdaptationAgent

        _adaptation_agent = AdaptationAgent(push_to_langsmith=False)
    return _adaptation_agent


def _get_assessment_agent():
    global _assessment_agent
    if _assessment_agent is None:
        from agents.assessment.skill_assessment_agent import SkillAssessmentAgent

        _assessment_agent = SkillAssessmentAgent(push_to_langsmith=False)
    return _assessment_agent


def _run_assessment(skill_graph: dict) -> Optional[dict]:
    """Generate the diagnostic MCQ quiz for a new path. Best-effort: any failure returns None so path
    creation never fails on the assessment (the frontend then just shows the graph directly)."""
    try:
        quiz = _get_assessment_agent().assess(json.dumps(skill_graph))
    except Exception:
        logger.exception("service: assessment generation failed; continuing without a quiz")
        return None
    if quiz is None or not quiz.questions:
        return None
    return {"quiz": quiz.model_dump(), "submitted": False}


class LockedNodeError(Exception):
    """Raised when a lesson is opened for a node whose prerequisites are not yet complete."""

    def __init__(self, node_id: str, pending: list):
        self.node_id = node_id
        self.pending = pending
        super().__init__(f"Node {node_id!r} is locked; complete first: {', '.join(pending)}")


def new_learning_session(final_state: dict, format_type: str) -> Optional[dict]:
    """Build a fresh ``learning_session`` dict from a SCOUT orchestration result.

    Returns ``None`` when no skill graph / nodes were produced. Shape is identical to the original
    ``app.py`` init block (maps 1:1 to the persisted JSONB row).
    """
    skill_graph = final_state.get("skill_graph")
    if not (skill_graph and skill_graph.get("nodes")):
        return None
    ls = {
        "skill_graph": skill_graph,
        "skill_graph_mermaid": final_state.get("skill_graph_mermaid"),
        "summary": skill_graph.get("summary"),
        "review_passed": final_state.get("review_passed"),
        "review_notes": final_state.get("review_notes"),
        "academic_output": final_state.get("academic_output"),
        "market_output": final_state.get("market_output"),
        "practical_output": final_state.get("practical_output"),
        "format_type": format_type,
        "node_state": {
            n["id"]: default_node_state() for n in skill_graph["nodes"]
        },
        "lessons": {},
        "selected_node": None,
        "chat": [],  # AI Teaching Assistant turns (P3 #10): list of {role, content}
    }
    # Diagnostic onboarding quiz (P2 #8): correct answers later pre-seed mastered nodes. Best-effort —
    # omitted entirely if generation fails, so the path still loads (frontend shows the graph directly).
    assessment = _run_assessment(skill_graph)
    if assessment is not None:
        ls["assessment"] = assessment
    return ls


def start_session(user_query: str, format_type: str = "B") -> dict:
    """Run the orchestration graph for a query and return the routed payload.

    Returns ``{"route", "learning_session", "final_content", "exercise"}``. Only the SCOUT route
    yields a persistable ``learning_session`` (the adaptive loop); CONTENT/EXERCISE are transient.
    """
    logger.info("service: start_session (query=%r, format=%s)", user_query, format_type)
    final_state = _run_async(
        _get_orchestration_graph().ainvoke({"user_query": user_query, "format_type": format_type})
    )
    route = final_state.get("route", "UNKNOWN")
    out = {"route": route, "learning_session": None, "final_content": None, "exercise": None}
    if route == "SCOUT":
        out["learning_session"] = new_learning_session(final_state, format_type)
    elif route == "CONTENT":
        out["final_content"] = final_state.get("final_content")
    elif route == "EXERCISE":
        if final_state.get("exercise_statement"):
            out["exercise"] = {
                "format": final_state.get("exercise_format"),
                "statement": final_state.get("exercise_statement"),
                "grading_artifact": final_state.get("grading_artifact"),
            }
    return out


def _run_lesson(
    node: dict, format_type: str, prior_weaknesses: list, user_id: Optional[str] = None
) -> dict:
    """Invoke the lesson graph for one skill node (content + embedded exercise)."""
    return _run_async(
        _get_lesson_graph().ainvoke(
            {
                "skill_label": node.get("label", ""),
                "skill_description": node.get("description", ""),
                "format_type": format_type,
                "prior_weaknesses": prior_weaknesses,
                "user_id": user_id,
            }
        )
    )


def open_lesson(ls: dict, node_id: str, user_id: Optional[str] = None) -> dict:
    """Compose (or reuse cached) the lesson for a node and mark it selected. Mutates and returns ls.

    Enforces prerequisite locking server-side: opening a locked node raises ``LockedNodeError`` so the
    gate cannot be bypassed by a client. A cached lesson is reused (cost guard — re-opening never
    rebuilds). ``user_id`` (when given) routes per-user RAG retrieval in the content sub-graph.
    """
    skill_graph = ls["skill_graph"]
    if node_id in locked_node_ids(skill_graph, ls["node_state"]):
        # A node deterministically locked by a sub-40 grade may have no remedial prerequisites yet (an
        # earlier adaptation LLM call failed). Re-attempt remediation now so the lock is never a
        # permanent dead-end, then re-evaluate before refusing.
        st = ls["node_state"].get(node_id, {})
        if st.get("remediation_pending") and not prereqs_by_node(skill_graph).get(node_id):
            logger.info("service: retrying remediation for flagged node %s on open", node_id)
            adapt_after_grade(ls, node_id)
            skill_graph = ls["skill_graph"]
        if node_id in locked_node_ids(skill_graph, ls["node_state"]):
            pending = incomplete_prereq_labels(skill_graph, ls["node_state"], node_id)
            logger.info("service: blocked locked lesson %s (pending=%s)", node_id, pending)
            raise LockedNodeError(node_id, pending)

    ls["selected_node"] = node_id
    if node_id not in ls["lessons"]:
        node = next(n for n in skill_graph["nodes"] if n["id"] == node_id)
        prior_weaknesses = ls["node_state"].get(node_id, {}).get("weaknesses", [])
        logger.info("service: composing lesson for node %s", node_id)
        out = _run_lesson(node, ls.get("format_type", "B"), prior_weaknesses, user_id)
        ls["lessons"][node_id] = {
            "content": out.get("content"),
            "exercise": {
                "format": out.get("exercise_format"),
                "statement": out.get("exercise_statement"),
                "grading_artifact": out.get("grading_artifact"),
            },
        }
    return ls


def adapt_after_grade(ls: dict, node_id: str) -> None:
    """Phase 3 — close the loop: a graded node mutates the graph (remedial nodes / unlock edges) and,
    on a low score, invalidates the cached lesson so the next open regenerates against the gaps.

    Runs only when the latest grade pushed the node to needs_review or mastered. LLM-backed; any
    failure is best-effort (the grade + mastery already persisted). Mutates ls in place.
    """
    state = ls["node_state"].get(node_id, {})
    if state.get("status") not in ("needs_review", "mastered"):
        return

    result = state.get("last_feedback") or {}
    score = float(result.get("score", 0.0) or 0.0)
    feedback = feedback_text(result)

    # Remediation (needs_review) gets bounded retries so the remedial prerequisites are near-certain to
    # land — the deterministic lock holds regardless, but we want an actual unlock path. The mastered
    # (unlock-edge) path is best-effort with a single try; its failure is harmless.
    attempts = 2 if state.get("status") == "needs_review" else 1
    logger.info("service: adapting graph after grade on node %s (score=%.0f)", node_id, score)
    adaptation = None
    for i in range(attempts):
        adaptation = _get_adaptation_agent().adapt(json.dumps(ls["skill_graph"]), node_id, score, feedback)
        if adaptation is not None and adaptation.new_nodes:
            break  # got remedial nodes — done
        if adaptation is not None and state.get("status") == "mastered":
            break  # unlock path: edges-only adaptation is fine without new nodes
    if adaptation is None:
        return

    from graph.skill_graph_adapt import apply_adaptation

    new_graph, new_ids = apply_adaptation(ls["skill_graph"], adaptation)
    ls["skill_graph"] = new_graph
    for nid in new_ids:
        ls["node_state"].setdefault(nid, default_node_state())

    focus = list(adaptation.remediation_focus or [])
    if focus:
        # Record the gaps on the graded node and drop its cached lesson so the next open regenerates
        # score-aware content. Clear last_feedback: the regenerated lesson carries a DIFFERENT
        # exercise, so the old grade panel would otherwise render a stale, mismatched result.
        ls["node_state"][node_id] = {**state, "weaknesses": focus, "last_feedback": None}
        ls["lessons"].pop(node_id, None)


def grade(ls: dict, node_id: str, solution: str) -> dict:
    """Grade a node's exercise submission, capture mastery, and run adaptation. Returns ls.

    Pulls the format + grading artifact from the cached lesson, so the caller passes only the raw
    solution string. Mutates and returns ls (caller persists the whole session afterward).
    """
    lesson = ls["lessons"].get(node_id)
    if not lesson:
        raise ValueError(f"No open lesson for node {node_id!r} to grade.")
    exercise = lesson.get("exercise") or {}
    fmt = exercise.get("format") or "coding_challenge"
    artifact = exercise.get("grading_artifact") or {}

    from agents.exercise.grader_agent import grade_submission

    logger.info("service: grading %s submission for node %s", fmt, node_id)
    result = grade_submission(fmt, solution, artifact)
    if result is not None:
        apply_score(ls, node_id, fmt, result)
        adapt_after_grade(ls, node_id)
    return ls


def grade_assessment(ls: dict, answers: list[int]) -> dict:
    """Grade the onboarding MCQ quiz; each correct answer pre-seeds that node as mastered. Returns ls.

    Reuses ``apply_score`` (sticky mastered). Wrong / unanswered (-1) leave the node at default
    ``available``. Does NOT run adaptation (no remedial nodes at onboarding). Mutates and returns ls.
    """
    assessment = ls.get("assessment")
    if not assessment or not assessment.get("quiz"):
        raise ValueError("No assessment quiz on this session.")
    questions = assessment["quiz"].get("questions", [])
    if len(answers) != len(questions):
        raise ValueError(f"Expected {len(questions)} answers, got {len(answers)}.")

    for q, ans in zip(questions, answers):
        if ans != q.get("correct_index"):
            continue  # wrong or skipped (-1) → leave node available
        node_id = q.get("node_id")
        # Guard: the LLM-supplied node_id must be a real node, else apply_score would create a phantom
        # node_state entry and corrupt the complete/total counter.
        if node_id not in ls["node_state"]:
            logger.warning("assessment: skipping unknown node_id %r from quiz", node_id)
            continue
        apply_score(ls, node_id, "mcq_assessment", {
            "score": 100,
            "feedback": "Passed the diagnostic assessment for this skill.",
        })
    assessment["submitted"] = True
    return ls


# --- AI Teaching Assistant (P3 #10) -----------------------------------------------------------

def _get_tutor_agent():
    global _tutor_agent
    if _tutor_agent is None:
        from agents.tutor.tutor_agent import TutorAgent

        _tutor_agent = TutorAgent()
    return _tutor_agent


def _node_label(ls: dict, node_id: Optional[str]) -> str:
    for n in ls.get("skill_graph", {}).get("nodes", []):
        if n.get("id") == node_id:
            return n.get("label", "")
    return ls.get("summary") or "this topic"


def build_tutor_messages(ls: dict, node_id: Optional[str], question: str, user_id: Optional[str]):
    """Assemble grounded chat messages: open-lesson content + the user's RAG material + prior history.

    Calls ``retrieve`` directly (no ``_run_async`` — this runs inside the route's event loop)."""
    lesson = (ls.get("lessons") or {}).get(node_id) or {}
    lesson_content = lesson.get("content")

    rag_context = None
    if user_id:
        try:
            from rag import registry

            store = registry.get_user_store(user_id)
            if store is not None and not store.is_empty:
                rag_context = store.retrieve(question)
        except Exception:
            logger.exception("tutor: RAG retrieval failed; continuing without it")

    return _get_tutor_agent().build_messages(
        skill_label=_node_label(ls, node_id),
        lesson_content=lesson_content,
        rag_context=rag_context,
        history=ls.get("chat", []),
        question=question,
    )
