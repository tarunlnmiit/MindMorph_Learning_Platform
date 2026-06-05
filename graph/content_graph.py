# LangGraph dual-path Content-Generation DAG (architecture §6.3).
#
#   START --> creative (Path A: engaging draft)
#   START --> factual  (Path B: live web search)
#   creative, factual --> synthesizer (Master LLM merges both) --> END
#
# Creative and factual write distinct state keys, so the parallel fan-out needs no reducer.

import sys
import os
from typing import Any, Optional, TypedDict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from langgraph.graph import StateGraph, START, END

from agents.content_generator.content_agent import ContentAgent
from agents.factual.factual_agent import FactualAgent
from agents.synthesizer.synthesizer_agent import SynthesizerAgent


class ContentState(TypedDict, total=False):
    user_query: str
    format_type: str          # 'A' Boost | 'B' Builder | 'C' Sprint
    prior_feedback: Optional[str]  # score-aware gap guidance; None = plain generation
    creative_draft: str
    factual_findings: Optional[str]
    final_content: str


def build_content_graph(
    content: Optional[Any] = None,
    factual: Optional[Any] = None,
    synthesizer: Optional[Any] = None,
):
    """Build and compile the dual-path content graph. Agents are injectable for tests."""
    content = content or ContentAgent(push_to_langsmith=False)
    factual = factual or FactualAgent()
    synthesizer = synthesizer or SynthesizerAgent(push_to_langsmith=False)

    def creative_node(state: ContentState) -> dict:
        fmt = state.get("format_type") or "B"
        return {
            "creative_draft": content.generate_content(
                state["user_query"], fmt, remediation=state.get("prior_feedback")
            )
        }

    def factual_node(state: ContentState) -> dict:
        return {"factual_findings": factual.gather_facts(state["user_query"])}

    def synthesizer_node(state: ContentState) -> dict:
        final = synthesizer.synthesize(
            state["user_query"],
            state.get("creative_draft", ""),
            state.get("factual_findings"),
        )
        return {"final_content": final}

    g = StateGraph(ContentState)
    g.add_node("creative", creative_node)
    g.add_node("factual", factual_node)
    g.add_node("synthesizer", synthesizer_node)

    g.add_edge(START, "creative")
    g.add_edge(START, "factual")
    g.add_edge("creative", "synthesizer")
    g.add_edge("factual", "synthesizer")
    g.add_edge("synthesizer", END)

    return g.compile()
