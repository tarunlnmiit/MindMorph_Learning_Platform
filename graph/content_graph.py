# LangGraph dual-path Content-Generation DAG (architecture §6.3).
#
#   START --> creative (Path A: engaging draft)
#   START --> factual  (Path B: live web search)
#   creative, factual --> synthesizer (Master LLM merges both) --> END
#
# Creative and factual write distinct state keys, so the parallel fan-out needs no reducer.

import logging
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

logger = logging.getLogger(__name__)


class ContentState(TypedDict, total=False):
    user_query: str
    format_type: str          # 'A' Boost | 'B' Builder | 'C' Sprint
    prior_feedback: Optional[str]  # score-aware gap guidance; None = plain generation
    creative_draft: str
    factual_findings: Optional[str]
    final_content: str


def _merge_findings(kb: Optional[str], web: Optional[str]) -> Optional[str]:
    """Combine knowledge-base + web grounding into one ``factual_findings`` string.

    Single-source returns that source **verbatim** (keeps the web-only / RAG-off path byte-identical);
    both present are labelled; both None → None (synthesizer degrades to the creative draft)."""
    if kb and web:
        return f"From the knowledge base:\n{kb}\n\nFrom the web:\n{web}"
    return kb or web


def _default_retriever() -> Optional[Any]:
    """Build the knowledge-base retriever when RAG is enabled, else None.

    Lazy: imports ``config``/``rag`` only here so the RAG-off path never loads fastembed."""
    import config

    if not getattr(config, "RAG_ENABLED", False):
        return None
    try:
        from rag.store import RagStore

        return RagStore.from_knowledge_dir(config.KNOWLEDGE_DIR)
    except Exception:
        logger.exception("RAG: failed to build default retriever; continuing web-only")
        return None


def build_content_graph(
    content: Optional[Any] = None,
    factual: Optional[Any] = None,
    synthesizer: Optional[Any] = None,
    retriever: Optional[Any] = None,
):
    """Build and compile the dual-path content graph. Agents are injectable for tests.

    ``retriever`` is an optional RAG store (``rag.store.RagStore``); when omitted, a default is built
    lazily from the knowledge base only if RAG is enabled (``config.RAG_ENABLED``). The retriever
    *augments* web search — it never replaces it.
    """
    content = content or ContentAgent(push_to_langsmith=False)
    factual = factual or FactualAgent()
    synthesizer = synthesizer or SynthesizerAgent(push_to_langsmith=False)
    retriever = retriever or _default_retriever()

    def creative_node(state: ContentState) -> dict:
        fmt = state.get("format_type") or "B"
        return {
            "creative_draft": content.generate_content(
                state["user_query"], fmt, remediation=state.get("prior_feedback")
            )
        }

    def factual_node(state: ContentState) -> dict:
        query = state["user_query"]
        web = factual.gather_facts(query)
        kb = retriever.retrieve(query) if retriever else None
        return {"factual_findings": _merge_findings(kb, web)}

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
