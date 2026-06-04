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

        if st.button("🚀 Generate Learning Path") and user_query:
            with st.status("Orchestrating agents...", expanded=True) as status:
                st.write("🤖 Running orchestration graph (orchestrate → scout → academic/market/practical)...")
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    final_state = loop.run_until_complete(
                        st.session_state.graph.ainvoke({"user_query": user_query})
                    )
                    loop.close()
                except Exception as e:
                    st.error(f"Graph execution failed: {e}")
                    st.stop()

                route = final_state.get("route", "UNKNOWN")
                st.write(f"Routing to: **{route}**")

                if route == "SCOUT":
                    status.update(label="✨ Learning Path Generated!", state="complete", expanded=False)

                    # Display Results
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
                else:
                    st.info(final_state.get("placeholder", f"Routed to {route}. Under development."))
                    status.update(label="Routing Complete", state="complete")

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
