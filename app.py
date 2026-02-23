import streamlit as st
import asyncio
import os
import sys
import json
from typing import Dict, Any

# Ensure project root is in path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from agents.orchertrator.orchestrator_agent import OrchestratorAgent
from agents.scout.scout_agent import ScoutAgent
from agents.market.market_agent import MarketAnalysisAgent
from agents.practical.practical_agent import PracticalAgent
from config import llm
import re

def extract_json(text):
    """Robustly extract JSON from a string that might contain other text or markdown."""
    try:
        # Try finding JSON block between ```json and ```
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        
        # Try finding JSON block between generic backticks
        json_match = re.search(r'```\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))

        # Try finding absolute first { and last }
        start_idx = text.find('{')
        end_idx = text.rfind('}') + 1
        if start_idx != -1 and end_idx != 0:
            return json.loads(text[start_idx:end_idx])
            
        return None
    except Exception:
        return None


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
                # Step 1: Orchestration
                st.write("🤖 Orchestrator: Analyzing query...")
                route_response = st.session_state.orchestrator.route_query(user_query)
                st.write(f"Routing to: **{route_response.Assigned_Agent}**")
                
                if route_response.Assigned_Agent == "SCOUT":
                    # Step 2: Scout Decomposition
                    st.write("🔍 Scout: Decomposing goal into specialized queries...")
                    scout_output = st.session_state.scout.generate_specialized_queries(user_query)
                    
                    if not scout_output:
                         st.error("Scout agent failed to generate specialized queries.")
                         st.stop()

                    # Handle structured output (Pydantic model) or fallback to text parsing
                    if isinstance(scout_output, dict):
                        queries = scout_output
                    elif hasattr(scout_output, 'model_dump'): # Pydantic v2
                        queries = scout_output.model_dump()
                    elif hasattr(scout_output, 'dict'): # Pydantic v1
                        queries = scout_output.dict()
                    else:
                        content = scout_output.content if hasattr(scout_output, 'content') else str(scout_output)
                        queries = extract_json(content)
                    
                    if not queries:
                         st.error("Scout output was not in the expected format.")
                         st.code(str(scout_output))
                         st.stop()


                    sub_queries = queries.get("sub_agent_queries", {})
                    st.write("✅ Specialized queries generated!")
                    
                    # Step 3: Sub-agent execution
                    market_data = None
                    practical_output = None
                    academic_output = None

                    st.write("📊 Market Analysis started...")
                    market_query = sub_queries.get("MARKET", user_query)
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        market_data = loop.run_until_complete(run_market_analysis(market_query))
                        loop.close()
                    except Exception as e:
                        st.error(f"Market Analysis failed: {e}")

                    st.write("🛠️ Practical Advice started...")
                    practical_query = sub_queries.get("PRACTICAL", user_query)
                    practical_output = st.session_state.practical.provide_practical_advice(practical_query)

                    st.write("📚 Academic Insights started...")
                    academic_query = sub_queries.get("ACADEMIC", user_query)
                    academic_output = llm.invoke(f"You are an Academic Agent. Provide a curriculum/learning roadmap for: {academic_query}")

                    status.update(label="✨ Learning Path Generated!", state="complete", expanded=False)

                    # Display Results
                    st.divider()
                    tab1, tab2, tab3 = st.tabs(["📚 Academic Roadmap", "💼 Market Intelligence", "🛠️ Practical Application"])

                    with tab1:
                        if academic_output: st.markdown(academic_output.content)
                        else: st.warning("Academic data could not be generated.")

                    with tab2:
                        if market_data:
                            job = market_data["job"]
                            st.subheader(f"{job.get('title')} at {job.get('organization')}")
                            st.markdown(market_data["summary"])
                            st.link_button("View Job Posting", job.get('url', '#'))
                        else: st.info("No specific job data found.")

                    with tab3:
                        if practical_output: st.markdown(practical_output.content)
                        else: st.warning("Practical advice could not be generated.")
                else:
                    st.info(f"Routed to {route_response.Assigned_Agent}. Under development.")
                    status.update(label="Routing Complete", state="complete")

    else: # Individual Agent Test Mode
        st.subheader("Test Individual Agents")
        agent_type = st.selectbox("Select Agent to Test", 
                                ["Orchestrator Agent", "Scout Agent", "Market Agent", "Practical Agent"])
        
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
