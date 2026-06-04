import streamlit as st
import asyncio
import os
import sys

# Ensure project root is in path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from agents.orchestrator.orchestrator_agent import OrchestratorAgent
from agents.scout.scout_agent import ScoutAgent
from agents.market.market_agent import MarketAnalysisAgent
from agents.practical.practical_agent import PracticalAgent
from agents.academic.academic_agent import AcademicAgent
from graph.learning_plan_graph import build_graph
import streamlit.components.v1 as components


def render_mermaid(mermaid_code: str, height: int = 520):
    """Render a Mermaid diagram by executing mermaid.js in an embedded HTML component.
    (st.markdown does not run mermaid; a raw ```mermaid block would show as text.)"""
    html = f"""
    <div class="mermaid">{mermaid_code}</div>
    <script type="module">
      import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
      mermaid.initialize({{ startOnLoad: true, theme: 'neutral' }});
    </script>
    """
    components.html(html, height=height, scrolling=True)


def render_exercise(exercise: dict):
    """Render a generated exercise + its grading harness, plus a submit-and-grade panel.

    Grading runs the learner's submission live: coding_challenge -> unit tests in a sandboxed
    subprocess; case_study -> LLM rubric scoring.
    """
    fmt = exercise.get("format") or "coding_challenge"
    artifact = exercise.get("grading_artifact") or {}

    st.subheader("🏋️ Practice Exercise")
    st.caption(f"Format: **{fmt}**")
    st.markdown(exercise.get("statement", ""))

    with st.expander("Grading harness", expanded=False):
        if artifact.get("instructions"):
            st.markdown(f"**Instructions:** {artifact['instructions']}")
        if fmt == "coding_challenge":
            tests = artifact.get("unit_tests") or []
            st.caption(f"{len(tests)} unit test(s) will run against your solution.")
            for i, t in enumerate(tests, 1):
                st.code(t, language="python")
        else:
            rubric = artifact.get("rubric") or []
            if rubric:
                st.table([{"Criterion": c.get("criterion"), "Weight": c.get("weight")} for c in rubric])

    st.divider()
    is_code = fmt == "coding_challenge"
    label = "Your solution (Python module defining the required name)" if is_code else "Your analysis"
    solution = st.text_area(label, height=220, key="exercise_solution")

    if st.button("Grade my submission", type="primary"):
        if not solution.strip():
            st.warning("Enter a solution first.")
        else:
            with st.spinner("Grading..."):
                # Imported lazily: keeps app import clean and isolates the code-execution surface.
                from agents.exercise.grader_agent import grade_submission
                result = grade_submission(fmt, solution, artifact)
            _render_grade_result(fmt, result)


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
                    st.error(f"Graph execution failed: {e}")
                    st.stop()

                route = final_state.get("route", "UNKNOWN")
                st.write(f"Routing to: **{route}**")

                if route == "SCOUT":
                    status.update(label="✨ Learning Path Generated!", state="complete", expanded=False)

                    # Skill Dependency Graph (Consensus) + Reviewer verdict
                    st.divider()
                    st.subheader("🗺️ Skill Dependency Graph")
                    mermaid = final_state.get("skill_graph_mermaid")
                    skill_graph = final_state.get("skill_graph")
                    if mermaid:
                        render_mermaid(mermaid)
                        if skill_graph and skill_graph.get("summary"):
                            st.caption(skill_graph["summary"])
                        with st.expander("Skill graph (JSON)"):
                            st.json(skill_graph)
                    else:
                        st.warning("Skill graph could not be generated.")

                    review_notes = final_state.get("review_notes")
                    if review_notes is not None:
                        passed = final_state.get("review_passed")
                        badge = "✅ Passed" if passed else "⚠️ Needs work"
                        st.markdown(f"**Reviewer:** {badge}")
                        st.info(review_notes)

                    # Specialist findings
                    st.divider()
                    tab1, tab2, tab3 = st.tabs(["📚 Academic Roadmap", "💼 Market Intelligence", "🛠️ Practical Application"])

                    with tab1:
                        academic_output = final_state.get("academic_output")
                        if academic_output: st.markdown(academic_output)
                        else: st.warning("Academic data could not be generated.")

                    with tab2:
                        market_data = final_state.get("market_output")
                        if market_data:
                            job = market_data["job"]
                            st.subheader(f"{job.get('title')} at {job.get('organization')}")
                            st.markdown(market_data["summary"])
                            st.link_button("View Job Posting", job.get('url', '#'))
                        else: st.info("No specific job data found.")

                    with tab3:
                        practical_output = final_state.get("practical_output")
                        if practical_output: st.markdown(practical_output)
                        else: st.warning("Practical advice could not be generated.")

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
