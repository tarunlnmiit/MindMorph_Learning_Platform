"""Dual-path content graph: creative + factual fan out (distinct keys) -> synthesizer."""
import os
import sys
from unittest.mock import MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from graph.content_graph import build_content_graph


async def test_content_graph_merges_both_paths():
    content = MagicMock()
    content.generate_content.return_value = "DRAFT"
    factual = MagicMock()
    factual.gather_facts.return_value = "FACTS"
    synthesizer = MagicMock()
    synthesizer.synthesize.return_value = "FINAL"

    graph = build_content_graph(content=content, factual=factual, synthesizer=synthesizer)
    state = await graph.ainvoke({"user_query": "Python lists", "format_type": "A"})

    assert state["creative_draft"] == "DRAFT"
    assert state["factual_findings"] == "FACTS"
    assert state["final_content"] == "FINAL"
    content.generate_content.assert_called_once_with("Python lists", "A", remediation=None)
    synthesizer.synthesize.assert_called_once_with("Python lists", "DRAFT", "FACTS")


async def test_content_graph_defaults_format_to_builder():
    content = MagicMock()
    content.generate_content.return_value = "DRAFT"
    factual = MagicMock()
    factual.gather_facts.return_value = None
    synthesizer = MagicMock()
    synthesizer.synthesize.return_value = "FINAL"

    graph = build_content_graph(content=content, factual=factual, synthesizer=synthesizer)
    await graph.ainvoke({"user_query": "Python lists"})

    content.generate_content.assert_called_once_with("Python lists", "B", remediation=None)


async def test_content_graph_threads_prior_feedback_as_remediation():
    content = MagicMock()
    content.generate_content.return_value = "DRAFT"
    factual = MagicMock()
    factual.gather_facts.return_value = None
    synthesizer = MagicMock()
    synthesizer.synthesize.return_value = "FINAL"

    graph = build_content_graph(content=content, factual=factual, synthesizer=synthesizer)
    await graph.ainvoke(
        {"user_query": "Python lists", "format_type": "A", "prior_feedback": "off-by-one errors"}
    )

    content.generate_content.assert_called_once_with(
        "Python lists", "A", remediation="off-by-one errors"
    )
