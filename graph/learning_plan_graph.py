# Top-level MindMorph LangGraph state graph.
#
#   START -> orchestrator -> (route)
#     SCOUT    -> scout -> [academic | market | practical] -> consensus -> reviewer -> END
#     CONTENT  -> content (dual-path content sub-graph) -> END
#     EXERCISE -> placeholder -> END   (Exercise DAG is P1, not yet built)
#
# The three specialists fan in to Consensus (one superstep join). Consensus emits a
# Skill Dependency Graph (JSON), the renderer turns it into Mermaid, and Reviewer checks it.
# Specialist / content nodes write distinct state keys, so fan-out needs no custom reducer.

import sys
import os
import json
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
from agents.consensus.consensus_agent import ConsensusAgent
from agents.reviewer.reviewer_agent import ReviewerAgent
from tools.github_mcp_client import MCPClientInitialization
from graph.content_graph import build_content_graph
from graph.exercise_graph import build_exercise_graph
from graph.skill_graph_render import skill_graph_to_mermaid


class LearningPlanState(TypedDict, total=False):
    """Shared state across both DAGs. Distinct keys per node => no custom reducer needed."""
    user_query: str
    format_type: str
    route: str
    reasoning: str
    # Learning-plan branch
    scout_queries: dict
    academic_output: Optional[str]
    market_output: Optional[dict]
    practical_output: Optional[str]
    skill_graph: Optional[dict]
    skill_graph_mermaid: Optional[str]
    review_passed: Optional[bool]
    review_notes: Optional[str]
    # Content branch
    creative_draft: Optional[str]
    factual_findings: Optional[str]
    final_content: Optional[str]
    # Exercise branch
    exercise_format: Optional[str]
    exercise_statement: Optional[str]
    grading_artifact: Optional[dict]
    # Non-SCOUT/CONTENT/EXERCISE routes
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
    """Port of app.py's run_market_analysis helper (the agent's own run_analysis only prints).

    The Scout MARKET query is a natural-language question; the job actor needs a concise
    role title, so we distill one before searching.
    """
    try:
        await market_agent.scraper.initialize()
        job_title = await market_agent.extract_job_title(query)
        dataset_id = await market_agent.scraper.search_jobs(job_title, location)
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
    consensus: Optional[Any] = None,
    reviewer: Optional[Any] = None,
    content: Optional[Any] = None,
    factual: Optional[Any] = None,
    synthesizer: Optional[Any] = None,
    format_selector: Optional[Any] = None,
    exercise_synthesizer: Optional[Any] = None,
    grader: Optional[Any] = None,
):
    """Build and compile the full MindMorph graph.

    All agents are injectable so tests can pass mocks; defaults are the real agents.
    The dual-path content sub-graph is built from (content, factual, synthesizer); the
    exercise sub-graph from (format_selector, exercise_synthesizer, grader).
    """
    orchestrator = orchestrator or OrchestratorAgent(push_to_langsmith=False)
    scout = scout or ScoutAgent(push_to_langsmith=False, output_variant="Query")
    academic = academic or AcademicAgent(push_to_langsmith=False)
    market = market or MarketAnalysisAgent()
    practical = practical or PracticalAgent(push_to_langsmith=False)
    consensus = consensus or ConsensusAgent(push_to_langsmith=False)
    reviewer = reviewer or ReviewerAgent(push_to_langsmith=False)
    content_graph = build_content_graph(content=content, factual=factual, synthesizer=synthesizer)
    exercise_graph = build_exercise_graph(
        format_selector=format_selector,
        synthesizer=exercise_synthesizer,
        grader=grader,
    )

    def orchestrator_node(state: LearningPlanState) -> dict:
        resp = orchestrator.route_query(state["user_query"])
        return {"route": resp.Assigned_Agent, "reasoning": resp.Reasoning}

    def route_condition(state: LearningPlanState) -> str:
        route = state.get("route")
        if route == "SCOUT":
            return "scout"
        if route == "CONTENT":
            return "content"
        if route == "EXERCISE":
            return "exercise"
        return "placeholder"

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

    def consensus_node(state: LearningPlanState) -> dict:
        market_data = state.get("market_output")
        market_text = market_data.get("summary") if market_data else None
        sg = consensus.build_skill_graph(
            state["user_query"],
            state.get("academic_output"),
            market_text,
            state.get("practical_output"),
        )
        if not sg:
            return {"skill_graph": None, "skill_graph_mermaid": ""}
        return {
            "skill_graph": sg.model_dump(),
            "skill_graph_mermaid": skill_graph_to_mermaid(sg),
        }

    def reviewer_node(state: LearningPlanState) -> dict:
        sg = state.get("skill_graph")
        if not sg:
            return {"review_passed": False, "review_notes": "No skill graph was produced to review."}
        res = reviewer.review_skill_graph(state["user_query"], json.dumps(sg))
        if not res:
            return {"review_passed": False, "review_notes": "Reviewer failed to evaluate the skill graph."}
        return {"review_passed": res.passed, "review_notes": res.notes}

    async def content_node(state: LearningPlanState) -> dict:
        out = await content_graph.ainvoke(
            {"user_query": state["user_query"], "format_type": state.get("format_type", "B")}
        )
        return {
            "creative_draft": out.get("creative_draft"),
            "factual_findings": out.get("factual_findings"),
            "final_content": out.get("final_content"),
        }

    async def exercise_node(state: LearningPlanState) -> dict:
        out = await exercise_graph.ainvoke({"user_query": state["user_query"]})
        return {
            "exercise_format": out.get("exercise_format"),
            "exercise_statement": out.get("exercise_statement"),
            "grading_artifact": out.get("grading_artifact"),
        }

    def placeholder_node(state: LearningPlanState) -> dict:
        return {"placeholder": f"Routed to {state.get('route')}. Under development."}

    g = StateGraph(LearningPlanState)
    g.add_node("orchestrator", orchestrator_node)
    g.add_node("scout", scout_node)
    g.add_node("academic", academic_node)
    g.add_node("market", market_node)
    g.add_node("practical", practical_node)
    g.add_node("consensus", consensus_node)
    g.add_node("reviewer", reviewer_node)
    g.add_node("content", content_node)
    g.add_node("exercise", exercise_node)
    g.add_node("placeholder", placeholder_node)

    g.add_edge(START, "orchestrator")
    g.add_conditional_edges(
        "orchestrator",
        route_condition,
        {"scout": "scout", "content": "content", "exercise": "exercise", "placeholder": "placeholder"},
    )
    # Learning-plan branch: fan out to specialists, fan in to consensus, then review.
    g.add_edge("scout", "academic")
    g.add_edge("scout", "market")
    g.add_edge("scout", "practical")
    g.add_edge("academic", "consensus")
    g.add_edge("market", "consensus")
    g.add_edge("practical", "consensus")
    g.add_edge("consensus", "reviewer")
    g.add_edge("reviewer", END)
    # Content branch.
    g.add_edge("content", END)
    # Exercise branch.
    g.add_edge("exercise", END)
    # Other routes.
    g.add_edge("placeholder", END)

    return g.compile()
