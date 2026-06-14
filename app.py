import streamlit as st
import asyncio
import json
import logging
import os
import sys

# Ensure project root is in path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from logging_config import setup_logging

setup_logging()  # configure root logging once, before any agent logs fire
logger = logging.getLogger(__name__)

from agents.orchestrator.orchestrator_agent import OrchestratorAgent
from agents.scout.scout_agent import ScoutAgent
from agents.market.market_agent import MarketAnalysisAgent
from agents.practical.practical_agent import PracticalAgent
from agents.academic.academic_agent import AcademicAgent
from graph.learning_plan_graph import build_graph
from graph.lesson_graph import build_lesson_graph
from graph.skill_graph_render import skill_graph_to_mermaid
from streamlit_ace import st_ace

# Mastery thresholds (Phase 2): score → node status.
MASTERY_THRESHOLD = 80   # >= mastered
REVIEW_THRESHOLD = 50    # >= in_progress, below ⇒ needs_review


def render_mermaid(mermaid_code: str, height: int = 520):
    """Render a Mermaid diagram by executing mermaid.js in an embedded iframe.
    (st.markdown does not run mermaid; a raw ```mermaid block would show as text.
    st.html strips <script>, so the raw-HTML iframe is required to run mermaid.js.)"""
    html = f"""
    <div class="mermaid">{mermaid_code}</div>
    <script type="module">
      import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
      mermaid.initialize({{ startOnLoad: true, theme: 'neutral' }});
    </script>
    """
    # st.iframe auto-detects a raw HTML string and embeds it (runs JS), replacing the
    # deprecated st.components.v1.html (removed in a future Streamlit release).
    st.iframe(html, height=height)


def render_exercise(exercise: dict, node_id: str | None = None, learning_session: dict | None = None):
    """Render a generated exercise + its grading harness, plus a submit-and-grade panel.

    Grading runs the learner's submission live: coding_challenge -> unit tests in a sandboxed
    subprocess; case_study -> LLM rubric scoring.

    Lesson path (node_id + learning_session given): the grade updates per-node mastery and the
    result is persisted in node_state['last_feedback'] so it survives the post-grade st.rerun()
    that re-colors the graph. Standalone EXERCISE route (node_id=None): transient render, no rerun.
    """
    is_lesson = node_id is not None and learning_session is not None
    # Per-node widget keys: Streamlit keys widget state globally, so a constant key would carry one
    # node's solution into another's editor and grade the wrong code into node_state. Scope by node.
    key_suffix = node_id or "standalone"
    fmt = exercise.get("format") or "coding_challenge"
    artifact = exercise.get("grading_artifact") or {}

    st.subheader("🏋️ Practice Exercise")
    st.caption(f"Format: **{fmt}**")
    st.markdown(exercise.get("statement", ""))

    with st.expander("Grading harness", expanded=False):
        if artifact.get("instructions"):
            st.markdown(f"**Instructions:** {artifact['instructions']}")
        if fmt == "coding_challenge":
            # The grader often returns unit_tests as per-line fragments; reconstruct the module
            # with "\n" (same join grade_submission uses to RUN them) so the harness shows as one
            # coherent block instead of one st.code box per line. Count real `def test`s, not lines.
            tests = artifact.get("unit_tests") or []
            test_module = "\n".join(tests)
            n_tests = test_module.count("def test") or len(tests)
            st.caption(f"{n_tests} unit test(s) will run against your solution.")
            if test_module.strip():
                st.code(test_module, language="python")
        else:
            rubric = artifact.get("rubric") or []
            if rubric:
                st.table([{"Criterion": c.get("criterion"), "Weight": c.get("weight")} for c in rubric])

    st.divider()
    is_code = fmt == "coding_challenge"
    if is_code:
        # Real in-browser code editor (Ace): syntax highlight, indent, line numbers. Returns the
        # code string straight to Python, so server-side hardened-sandbox grading is unchanged.
        st.caption("Your solution (Python module defining the required name)")
        solution = st_ace(
            language="python",
            theme="monokai",
            height=280,
            font_size=14,
            tab_size=4,
            show_gutter=True,
            auto_update=True,  # return edits without an explicit save keystroke
            placeholder="# Write your solution here",
            key=f"exercise_solution_ace_{key_suffix}",
        )
    else:
        solution = st.text_area("Your analysis", height=220, key=f"exercise_solution_{key_suffix}")

    if st.button("Grade my submission", type="primary", key=f"grade_btn_{key_suffix}"):
        if not (solution or "").strip():
            st.warning("Enter a solution first.")
        else:
            logger.info("UI: grading %s submission", fmt)
            with st.spinner("Grading..."):
                # Imported lazily: keeps app import clean and isolates the code-execution surface.
                from agents.exercise.grader_agent import grade_submission
                result = grade_submission(fmt, solution, artifact)
            if is_lesson and result is not None:
                # Capture mastery, then rerun so the graph re-colors + progress updates; the
                # persisted last_feedback (rendered below) makes the result reappear after rerun.
                _apply_score(learning_session, node_id, fmt, result)
                # Phase 3: close the loop — mutate the graph (remedial nodes / unlock edges) and
                # invalidate this node's cached lesson on a low score, before the re-render.
                with st.spinner("Adapting your roadmap..."):
                    _adapt_after_grade(learning_session, node_id)
                st.rerun()
            else:
                _render_grade_result(fmt, result)

    # Lesson path: re-render the last grade result from state (survives the post-grade rerun).
    if is_lesson:
        prior = learning_session["node_state"].get(node_id, {}).get("last_feedback")
        if prior is not None:
            _render_grade_result(fmt, prior)


def _render_grade_result(fmt: str, result):
    if result is None:
        st.error("Grading failed.")
        return
    if fmt == "coding_challenge":
        passed, total = result.get("passed", 0), result.get("total", 0)
        score = result.get("score", 0.0)
        (st.success if passed == total and total > 0 else st.error)(
            f"{passed}/{total} tests passed — score {score:.0f}%"
        )
        if result.get("timed_out"):
            st.warning("Execution timed out (possible infinite loop).")
        for f in result.get("failures", []):
            st.code(f, language="text")
        if result.get("stdout"):
            with st.expander("Test output"):
                st.code(result["stdout"], language="text")
    else:
        st.success(f"Score: {result.get('score', 0):.0f}%")
        for line in result.get("per_criterion", []):
            st.markdown(f"- {line}")
        if result.get("feedback"):
            st.markdown(f"**Feedback:** {result['feedback']}")


def _apply_score(ls: dict, node_id: str, fmt: str, result: dict) -> None:
    """Phase 2 — write a grade result into learning_session['node_state'][node_id].

    Pure state update (builds a new node_state entry, no Streamlit calls) so it's unit-testable
    without a Streamlit context. Both coding_challenge and case_study expose 'score' (0–100).
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


def _default_node_state() -> dict:
    """Fresh node_state entry (matches the SCOUT-init shape) for newly added remedial nodes."""
    return {"status": "available", "best_score": 0, "attempts": 0, "weaknesses": [], "last_feedback": None}


def _feedback_text(result: dict | None) -> str:
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


def _adapt_after_grade(ls: dict, node_id: str) -> None:
    """Phase 3 — close the loop: a graded node mutates the graph (remedial nodes / unlock edges)
    and, on a low score, invalidates the cached lesson so the next open regenerates against the gaps.

    Runs only when the latest grade pushed the node to needs_review or mastered. LLM-backed; any
    failure is swallowed (the grade + mastery already persisted — adaptation is best-effort).
    """
    state = ls["node_state"].get(node_id, {})
    if state.get("status") not in ("needs_review", "mastered"):
        return

    result = state.get("last_feedback") or {}
    score = float(result.get("score", 0.0) or 0.0)
    feedback = _feedback_text(result)

    agent = st.session_state.get("adaptation_agent")
    if agent is None:
        from agents.adaptation.adaptation_agent import AdaptationAgent
        agent = AdaptationAgent(push_to_langsmith=False)
        st.session_state.adaptation_agent = agent

    logger.info("UI: adapting graph after grade on node %s (score=%.0f)", node_id, score)
    adaptation = agent.adapt(json.dumps(ls["skill_graph"]), node_id, score, feedback)
    if adaptation is None:
        return

    from graph.skill_graph_adapt import apply_adaptation
    new_graph, new_ids = apply_adaptation(ls["skill_graph"], adaptation)
    ls["skill_graph"] = new_graph
    for nid in new_ids:
        ls["node_state"].setdefault(nid, _default_node_state())

    focus = list(adaptation.remediation_focus or [])
    if focus:
        # Record the gaps on the graded node and drop its cached lesson so the next open
        # regenerates score-aware content (weaknesses -> prior_feedback -> generate_content remediation).
        # Also clear last_feedback: the regenerated lesson carries a DIFFERENT exercise, so the old
        # grade panel would otherwise render a stale, mismatched result against the new harness.
        ls["node_state"][node_id] = {**state, "weaknesses": focus, "last_feedback": None}
        ls["lessons"].pop(node_id, None)


# CSS for better styling
st.markdown("""
<style>
    .main {
        background-color: #f5f7f9;
    }
    .stAlert {
        border-radius: 10px;
    }
    .agent-card {
        padding: 20px;
        border-radius: 10px;
        background-color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 20px;
        border: 1px solid #e0e0e0;
    }
</style>
""", unsafe_allow_html=True)

def initialize_agents():
    """Initialize agents and store in session state"""
    if 'orchestrator' not in st.session_state:
        st.session_state.orchestrator = OrchestratorAgent(push_to_langsmith=False)
    if 'scout' not in st.session_state:
        st.session_state.scout = ScoutAgent(push_to_langsmith=False, output_variant="Query")
    if 'market' not in st.session_state:
        st.session_state.market = MarketAnalysisAgent()
    if 'practical' not in st.session_state:
        st.session_state.practical = PracticalAgent(push_to_langsmith=False)
    if 'academic' not in st.session_state:
        st.session_state.academic = AcademicAgent(push_to_langsmith=False)
    if 'graph' not in st.session_state:
        st.session_state.graph = build_graph(
            orchestrator=st.session_state.orchestrator,
            scout=st.session_state.scout,
            academic=st.session_state.academic,
            market=st.session_state.market,
            practical=st.session_state.practical,
        )
    if 'lesson_graph' not in st.session_state:
        # Composes the content + exercise sub-graphs; one click = one lesson for a skill node.
        st.session_state.lesson_graph = build_lesson_graph()

async def run_market_analysis(query: str, location: str = "United States"):
    """Helper to run async market analysis"""
    agent = st.session_state.market
    await agent.scraper.initialize()
    dataset_id = await agent.scraper.search_jobs(query, location)
    if dataset_id:
        jobs = await agent.scraper.fetch_job_results(dataset_id)
        if jobs:
            summary = await agent.summarize_job(jobs[0])
            return {"job": jobs[0], "summary": summary}
    return None


def _node_label_map(skill_graph: dict) -> dict:
    """Map node_id -> label for the skill picker (ids are unique; labels may repeat)."""
    return {n["id"]: n.get("label", n["id"]) for n in skill_graph.get("nodes", [])}


# Picker ordering: foundational -> intermediate -> advanced. Phase 3 appends remedial nodes to the
# end of the nodes list, which left them dangling at the bottom of the selectbox even though they sit
# early (as new prerequisites) in the graph. Sorting by level rank (stable within a level, so the
# original consensus order is preserved) realigns the picker with the graph's reading order.
_LEVEL_RANK = {"foundational": 0, "intermediate": 1, "advanced": 2}


def _ordered_node_ids(skill_graph: dict) -> list:
    nodes = skill_graph.get("nodes", [])
    return [
        n["id"]
        for n in sorted(nodes, key=lambda n: _LEVEL_RANK.get((n.get("level") or "").lower(), 1))
    ]


# --- Prerequisite-gated completion ------------------------------------------------------------
# Per-node mastery (best_score >= 80, sticky) is the underlying truth. "Complete" is derived: a node
# counts as complete only when it AND all its prerequisites (transitively) are mastered. A node that
# passed its own exercise but still has an incomplete prerequisite renders 🔒 ("blocked"), not ✅, and
# is excluded from the progress count — so completion reflects the whole dependency chain.


def _prereqs_by_node(skill_graph: dict) -> dict:
    """Map node_id -> set of its prerequisite ids. Edge convention (SkillEdge): source = prerequisite,
    target = the skill that depends on it. So prereqs of X = sources of edges whose target is X."""
    prereqs: dict = {n["id"]: set() for n in skill_graph.get("nodes", [])}
    for e in skill_graph.get("edges", []) or []:
        src, tgt = e.get("source"), e.get("target")
        if tgt in prereqs and src is not None:
            prereqs[tgt].add(src)
    return prereqs


def _complete_node_ids(skill_graph: dict, node_state: dict) -> set:
    """Set of node ids that are fully complete: mastered AND every prerequisite complete (recursive).

    Memoized with a cycle guard — a node currently being resolved is treated as not-complete, so a
    cyclic graph returns instead of recursing forever (the graph is meant to be acyclic).
    """
    prereqs = _prereqs_by_node(skill_graph)

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


def _locked_node_ids(skill_graph: dict, node_state: dict) -> set:
    """Set of node ids that are LOCKED: at least one direct prerequisite is not complete.

    A learner may not open a locked node's lesson. Transitivity is automatic — completion is
    transitive, so a node downstream of an unmastered node has an incomplete prerequisite and is
    locked too. Root nodes (no prerequisites) and complete nodes are never locked.
    """
    complete = _complete_node_ids(skill_graph, node_state)
    prereqs = _prereqs_by_node(skill_graph)
    return {nid for nid, ps in prereqs.items() if any(p not in complete for p in ps)}


def _incomplete_prereq_labels(skill_graph: dict, node_state: dict, node_id: str) -> list:
    """Labels of a node's direct prerequisites that are not yet complete (for the lock message)."""
    complete = _complete_node_ids(skill_graph, node_state)
    label_by_id = _node_label_map(skill_graph)
    prereqs = _prereqs_by_node(skill_graph).get(node_id, set())
    return [label_by_id.get(p, p) for p in prereqs if p not in complete]


def _display_status(skill_graph: dict, node_state: dict) -> dict:
    """node_id -> status handed to the renderer. Complete -> 'mastered' (✅); any node with an
    incomplete prerequisite (locked) -> 'blocked' (🔒); otherwise the underlying status (unchanged).
    The mastered-but-prereq-pending case is a subset of locked, so its 🔒 behavior is preserved."""
    complete = _complete_node_ids(skill_graph, node_state)
    locked = _locked_node_ids(skill_graph, node_state)
    out: dict = {}
    for nid, s in node_state.items():
        if nid in complete:
            out[nid] = "mastered"
        elif nid in locked:
            out[nid] = "blocked"
        else:
            out[nid] = s.get("status")
    return out


def run_lesson(node: dict, format_type: str, prior_weaknesses: list):
    """Run the lesson graph for one clicked skill node (content + exercise). Sync wrapper."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(
            st.session_state.lesson_graph.ainvoke(
                {
                    "skill_label": node.get("label", ""),
                    "skill_description": node.get("description", ""),
                    "format_type": format_type,
                    "prior_weaknesses": prior_weaknesses,
                }
            )
        )
    finally:
        loop.close()


def render_learning_session():
    """Render the interactive SCOUT result: skill graph + node picker + composed lesson.

    Persists across Streamlit reruns via st.session_state.learning_session, so the selectbox
    and Open-lesson interactions survive without re-running the orchestration graph.
    """
    ls = st.session_state.learning_session
    skill_graph = ls["skill_graph"]
    nodes = skill_graph.get("nodes", [])
    if not nodes:
        st.warning("Skill graph could not be generated.")
        return

    node_state = ls["node_state"]
    # Prerequisite-gated completion: a node counts only when it AND its prerequisites are mastered.
    complete = _complete_node_ids(skill_graph, node_state)

    st.divider()
    st.subheader(f"🎯 {len(complete)} / {len(nodes)} skills complete")
    # Live recompute with the status overlay (deterministic, no LLM cost) so node colors/glyphs
    # reflect the latest grades. _display_status downgrades a mastered-but-prereq-incomplete node to
    # 🔒 'blocked'. The stored skill_graph_mermaid (status-free) is left as a fallback.
    node_status = _display_status(skill_graph, node_state)
    mermaid = skill_graph_to_mermaid(skill_graph, node_status)
    if mermaid:
        render_mermaid(mermaid)
    if ls.get("summary"):
        st.caption(ls["summary"])
    with st.expander("Skill graph (JSON)"):
        st.json(skill_graph)

    if ls.get("review_notes") is not None:
        badge = "✅ Passed" if ls.get("review_passed") else "⚠️ Needs work"
        st.markdown(f"**Reviewer:** {badge}")
        st.info(ls["review_notes"])

    # --- Node picker (selectbox alongside the Mermaid; iframe can't report Mermaid clicks) ---
    st.divider()
    st.subheader("📖 Study a Skill")
    label_by_id = _node_label_map(skill_graph)
    node_ids = _ordered_node_ids(skill_graph)
    # Locked nodes (a prerequisite isn't complete) are prefixed 🔒 in the picker and can't be opened.
    locked = _locked_node_ids(skill_graph, node_state)
    selected_id = st.selectbox(
        "Pick a skill to study",
        node_ids,
        format_func=lambda i: (f"🔒 {label_by_id[i]}" if i in locked else label_by_id[i]),
        key="lesson_node_picker",
    )
    if st.button("📖 Open lesson", type="primary"):
        if selected_id in locked:
            # Gate access: don't open a locked lesson; tell the learner what to finish first.
            # selected_node is left unchanged so no stale lesson renders below.
            pending = _incomplete_prereq_labels(skill_graph, node_state, selected_id)
            logger.info("UI: blocked locked lesson %s (pending=%s)", selected_id, pending)
            st.warning("🔒 Locked — first complete: " + ", ".join(pending))
        else:
            ls["selected_node"] = selected_id
            if selected_id not in ls["lessons"]:
                node = next(n for n in nodes if n["id"] == selected_id)
                prior_weaknesses = ls["node_state"].get(selected_id, {}).get("weaknesses", [])
                logger.info("UI: opening lesson for node %s (%r)", selected_id, label_by_id[selected_id])
                with st.spinner(f"Composing lesson for '{label_by_id[selected_id]}'..."):
                    try:
                        out = run_lesson(node, ls.get("format_type", "B"), prior_weaknesses)
                        ls["lessons"][selected_id] = {
                            "content": out.get("content"),
                            "exercise": {
                                "format": out.get("exercise_format"),
                                "statement": out.get("exercise_statement"),
                                "grading_artifact": out.get("grading_artifact"),
                            },
                        }
                    except Exception as e:
                        logger.exception("UI: lesson generation failed for node %s", selected_id)
                        st.error(f"Lesson generation failed: {e}")
            # No st.rerun(): the button press already triggered this run; on success we fall
            # through to render the just-cached lesson below, and on failure the error stays visible.

    # --- Render the open lesson (content + embedded exercise at the end) ---
    open_id = ls.get("selected_node")
    if open_id and open_id in ls["lessons"]:
        lesson = ls["lessons"][open_id]
        st.divider()
        st.markdown(f"### {label_by_id.get(open_id, open_id)}")
        if lesson.get("content"):
            st.markdown(lesson["content"])
        else:
            st.warning("Lesson content could not be generated.")
        if lesson.get("exercise", {}).get("statement"):
            render_exercise(lesson["exercise"], node_id=open_id, learning_session=ls)

    # --- Specialist findings (collapsed; the roadmap is secondary to the interactive lesson) ---
    with st.expander("📋 Roadmap details (Academic / Market / Practical)", expanded=False):
        tab1, tab2, tab3 = st.tabs(["📚 Academic Roadmap", "💼 Market Intelligence", "🛠️ Practical Application"])
        with tab1:
            academic_output = ls.get("academic_output")
            if academic_output:
                st.markdown(academic_output)
            else:
                st.warning("Academic data could not be generated.")
        with tab2:
            market_data = ls.get("market_output")
            if market_data:
                job = market_data["job"]
                st.subheader(f"{job.get('title')} at {job.get('organization')}")
                st.markdown(market_data["summary"])
                st.link_button("View Job Posting", job.get("url", "#"))
            else:
                st.info("No specific job data found.")
        with tab3:
            practical_output = ls.get("practical_output")
            if practical_output:
                st.markdown(practical_output)
            else:
                st.warning("Practical advice could not be generated.")


def main():
    st.set_page_config(page_title="MindMorph Learning Platform", layout="wide")
    st.title("🧠 MindMorph Learning Platform")
    
    with st.sidebar:
        st.header("⚙️ Configuration")
        app_mode = st.radio("Select Mode", ["Full Orchestration", "Individual Agent Test"])
        
        st.divider()
        st.info("Ensure GROQ_API_KEY and APIFY_API_KEY are set in your .env file.")
        if st.button("🔄 Re-initialize Agents"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    initialize_agents()

    if app_mode == "Full Orchestration":
        st.subheader("Generate a Complete Learning Roadmap")
        user_query = st.text_input("What do you want to learn today?", placeholder="e.g., Learn Python for Data Science")
        fmt_label = st.radio(
            "Lesson depth (used when the query routes to CONTENT)",
            ["A — 5-min Boost", "B — 20-min Builder", "C — 2-hour Sprint"],
            index=1,
            horizontal=True,
        )
        format_type = fmt_label.split(" ")[0]

        if st.button("🚀 Generate Learning Path") and user_query:
            logger.info("UI: generate requested (query=%r, format=%s)", user_query, format_type)
            with st.status("Orchestrating agents...", expanded=True) as status:
                st.write("🤖 Running orchestration graph (orchestrate → scout → specialists → consensus → reviewer)...")
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    final_state = loop.run_until_complete(
                        st.session_state.graph.ainvoke(
                            {"user_query": user_query, "format_type": format_type}
                        )
                    )
                    loop.close()
                except Exception as e:
                    logger.exception("UI: graph execution failed")
                    st.error(f"Graph execution failed: {e}")
                    st.stop()

                route = final_state.get("route", "UNKNOWN")
                logger.info("UI: orchestration complete, route=%s", route)
                st.write(f"Routing to: **{route}**")

                if route == "SCOUT":
                    status.update(label="✨ Learning Path Generated!", state="complete", expanded=False)
                    skill_graph = final_state.get("skill_graph")
                    if skill_graph and skill_graph.get("nodes"):
                        # Store the interactive learning session; rendering happens outside the
                        # generate-button block so the picker/lesson survive Streamlit reruns.
                        st.session_state.learning_session = {
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
                                n["id"]: {
                                    "status": "available",
                                    "best_score": 0,
                                    "attempts": 0,
                                    "weaknesses": [],
                                    "last_feedback": None,
                                }
                                for n in skill_graph["nodes"]
                            },
                            "lessons": {},
                            "selected_node": None,
                        }
                        # A fresh path supersedes any prior standalone exercise panel.
                        st.session_state.pop("exercise", None)
                    else:
                        st.session_state.pop("learning_session", None)
                        st.warning("Skill graph could not be generated.")

                elif route == "CONTENT":
                    status.update(label="✨ Lesson Generated!", state="complete", expanded=False)
                    st.divider()
                    final_content = final_state.get("final_content")
                    if final_content:
                        grounded = bool(final_state.get("factual_findings"))
                        st.caption("Dual-path: creative draft + " + ("live web grounding" if grounded else "no live grounding (creative only)"))
                        st.markdown(final_content)
                    else:
                        st.warning("Content could not be generated.")

                elif route == "EXERCISE":
                    status.update(label="🏋️ Exercise Generated!", state="complete", expanded=False)
                    st.divider()
                    statement = final_state.get("exercise_statement")
                    if statement:
                        # Persist so the grading step survives Streamlit reruns (Phase B).
                        st.session_state.exercise = {
                            "format": final_state.get("exercise_format"),
                            "statement": statement,
                            "grading_artifact": final_state.get("grading_artifact"),
                        }
                    else:
                        status.update(label="Exercise generation incomplete", state="error")
                        st.warning(
                            "A generation step returned nothing — usually a transient LLM hiccup. "
                            "Click **🚀 Generate Learning Path** again to retry."
                        )

                else:
                    st.info(final_state.get("placeholder", f"Routed to {route}. Under development."))
                    status.update(label="Routing Complete", state="complete")

        # Interactive learning session (SCOUT): skill graph + node picker + composed lesson.
        # Rendered outside the generate block so picker/lesson interactions persist across reruns.
        if st.session_state.get("learning_session"):
            render_learning_session()

        # Exercise + grading panel (outside the spinner; persists across reruns for the Grade action).
        if st.session_state.get("exercise"):
            render_exercise(st.session_state.exercise)

    else: # Individual Agent Test Mode
        st.subheader("Test Individual Agents")
        agent_type = st.selectbox("Select Agent to Test",
                                ["Orchestrator Agent", "Scout Agent", "Academic Agent", "Market Agent", "Practical Agent"])
        
        test_query = st.text_area("Enter Test Query", height=100)
        
        if st.button("▶️ Run Agent") and test_query:
            with st.spinner(f"Running {agent_type}..."):
                try:
                    if agent_type == "Orchestrator Agent":
                        result = st.session_state.orchestrator.route_query(test_query)
                        st.json({"Assigned_Agent": result.Assigned_Agent, "Reasoning": result.Reasoning})
                        
                    elif agent_type == "Scout Agent":
                        result = st.session_state.scout.generate_specialized_queries(test_query)
                        if result:
                            if hasattr(result, 'model_dump'):
                                st.json(result.model_dump())
                            elif hasattr(result, 'dict'):
                                st.json(result.dict())
                            else:
                                st.code(str(result))
                        else:
                            st.error("Agent failed to return a result.")


                        
                    elif agent_type == "Academic Agent":
                        result = st.session_state.academic.provide_academic_roadmap(test_query)
                        if result: st.markdown(result.content)
                        else: st.error("Agent failed to return a result.")

                    elif agent_type == "Market Agent":
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        result = loop.run_until_complete(run_market_analysis(test_query))
                        loop.close()
                        if result:
                            st.subheader(f"Example Opening: {result['job'].get('title')}")
                            st.markdown(result['summary'])
                        else:
                            st.warning("No market data found.")
                            
                    elif agent_type == "Practical Agent":
                        result = st.session_state.practical.provide_practical_advice(test_query)
                        st.markdown(result.content)
                        
                except Exception as e:
                    st.error(f"Agent Execution Error: {e}")

if __name__ == "__main__":
    main()
