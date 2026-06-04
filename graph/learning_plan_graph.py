# LangGraph state graph for the Learning-Plan (SCOUT) DAG.
#
# Replaces the hardcoded sequential orchestration that used to live inside app.py's
# Streamlit button handler. The Orchestrator routes; on the SCOUT route the Scout
# decomposes the goal and three specialist nodes (Academic / Market / Practical) run
# in parallel, each writing its own state key. CONTENT / EXERCISE routes terminate at a
# placeholder node until their DAGs are implemented.

import sys
import os
from typing import Any, Optional, TypedDict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from langgraph.graph import StateGraph, START, END

from agents.orchestrator.orchestrator_agent import OrchestratorAgent
from agents.scout.scout_agent import ScoutAgent
from agents.academic.academic_agent import AcademicAgent
from agents.market.market_agent import MarketAnalysisAgent
from agents.practical.practical_agent import PracticalAgent
from tools.github_mcp_client import MCPClientInitialization


class LearningPlanState(TypedDict, total=False):
    """Shared state. Specialist nodes write distinct keys so the parallel fan-out
    needs no custom reducer."""
    user_query: str
    route: str
    reasoning: str
    scout_queries: dict
    academic_output: Optional[str]
    market_output: Optional[dict]
    practical_output: Optional[str]
    placeholder: Optional[str]


# --- helpers -------------------------------------------------------------------

def _normalize_scout_queries(scout_output: Any) -> dict:
    """Coerce the Scout's structured output into a plain {ACADEMIC, MARKET, PRACTICAL} dict."""
    if scout_output is None:
        return {}
    if hasattr(scout_output, "model_dump"):
        data = scout_output.model_dump()
    elif hasattr(scout_output, "dict"):
        data = scout_output.dict()
    elif isinstance(scout_output, dict):
        data = scout_output
    else:
        return {}
    return data.get("sub_agent_queries", {}) or {}


async def _run_market(market_agent: Any, query: str, location: str = "United States") -> Optional[dict]:
    """Port of app.py's run_market_analysis helper (the agent's own run_analysis only prints)."""
    try:
        await market_agent.scraper.initialize()
        dataset_id = await market_agent.scraper.search_jobs(query, location)
        if not dataset_id:
            return None
        jobs = await market_agent.scraper.fetch_job_results(dataset_id)
        if not jobs:
            return None
        summary = await market_agent.summarize_job(jobs[0])
        return {"job": jobs[0], "summary": summary}
    except Exception as e:
        print(f"Market node error: {e}")
        return None


async def _fetch_github_repos(query: str) -> Optional[Any]:
    """Resilient GitHub MCP lookup. Returns None (no hard failure) when token/network is absent."""
    try:
        client = MCPClientInitialization()
        if not client.token:
            return None
        await client.initialize()
        return await client.search_github_repositories(query)
    except Exception as e:
        print(f"GitHub repo fetch error: {e}")
        return None


# --- graph builder -------------------------------------------------------------

def build_graph(
    orchestrator: Optional[Any] = None,
    scout: Optional[Any] = None,
    academic: Optional[Any] = None,
    market: Optional[Any] = None,
    practical: Optional[Any] = None,
):
    """Build and compile the Learning-Plan graph.

    Agents are injectable so tests can pass mocks; defaults are the real agents.
    """
    orchestrator = orchestrator or OrchestratorAgent(push_to_langsmith=False)
    scout = scout or ScoutAgent(push_to_langsmith=False, output_variant="Query")
    academic = academic or AcademicAgent(push_to_langsmith=False)
    market = market or MarketAnalysisAgent()
    practical = practical or PracticalAgent(push_to_langsmith=False)

    def orchestrator_node(state: LearningPlanState) -> dict:
        resp = orchestrator.route_query(state["user_query"])
        return {"route": resp.Assigned_Agent, "reasoning": resp.Reasoning}

    def route_condition(state: LearningPlanState) -> str:
        return "scout" if state.get("route") == "SCOUT" else "placeholder"

    def scout_node(state: LearningPlanState) -> dict:
        out = scout.generate_specialized_queries(state["user_query"])
        return {"scout_queries": _normalize_scout_queries(out)}

    def academic_node(state: LearningPlanState) -> dict:
        query = state.get("scout_queries", {}).get("ACADEMIC") or state["user_query"]
        resp = academic.provide_academic_roadmap(query)
        return {"academic_output": resp.content if resp else None}

    async def market_node(state: LearningPlanState) -> dict:
        query = state.get("scout_queries", {}).get("MARKET") or state["user_query"]
        return {"market_output": await _run_market(market, query)}

    async def practical_node(state: LearningPlanState) -> dict:
        query = state.get("scout_queries", {}).get("PRACTICAL") or state["user_query"]
        repos = await _fetch_github_repos(query)
        resp = practical.provide_practical_advice(query, github_repos=repos)
        return {"practical_output": resp.content if resp else None}

    def placeholder_node(state: LearningPlanState) -> dict:
        return {"placeholder": f"Routed to {state.get('route')}. Under development."}

    g = StateGraph(LearningPlanState)
    g.add_node("orchestrator", orchestrator_node)
    g.add_node("scout", scout_node)
    g.add_node("academic", academic_node)
    g.add_node("market", market_node)
    g.add_node("practical", practical_node)
    g.add_node("placeholder", placeholder_node)

    g.add_edge(START, "orchestrator")
    g.add_conditional_edges(
        "orchestrator",
        route_condition,
        {"scout": "scout", "placeholder": "placeholder"},
    )
    # Fan out to the three specialists (parallel), each joins to END.
    g.add_edge("scout", "academic")
    g.add_edge("scout", "market")
    g.add_edge("scout", "practical")
    g.add_edge("academic", END)
    g.add_edge("market", END)
    g.add_edge("practical", END)
    g.add_edge("placeholder", END)

    return g.compile()
