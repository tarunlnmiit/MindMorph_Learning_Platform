"""Phase 3 — AdaptationAgent: structured-output call (mocked LLM, no network)."""
import os
import sys
from unittest.mock import MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from agents.adaptation.adaptation_agent import AdaptationAgent
from agents.adaptation.adaptation_schema import GraphAdaptation

_GRAPH_JSON = '{"summary":"x","nodes":[{"id":"loops","label":"Loops","description":"d","level":"foundational"}],"edges":[]}'


def _agent_with_result(result):
    agent = AdaptationAgent.__new__(AdaptationAgent)  # skip real __init__ (no llm/network)
    agent.structured_llm = MagicMock()
    agent.structured_llm.invoke.return_value = result
    agent.chat_prompt = MagicMock()
    agent.chat_prompt.format_messages.return_value = []
    return agent


def test_low_score_returns_remedial_adaptation():
    result = GraphAdaptation(
        new_nodes=[{"id": "loop_basics", "label": "Loop Basics", "description": "d", "level": "foundational"}],
        new_edges=[{"source": "loop_basics", "target": "loops", "relation": "prerequisite"}],
        remediation_focus=["off-by-one"],
        rationale="struggled",
    )
    agent = _agent_with_result(result)
    out = agent.adapt(_GRAPH_JSON, "loops", 20.0, "off-by-one errors")
    assert out.new_nodes[0].id == "loop_basics"
    assert out.remediation_focus == ["off-by-one"]


def test_high_score_returns_unlock_only():
    result = GraphAdaptation(new_nodes=[], new_edges=[{"source": "loops", "target": "funcs"}],
                             remediation_focus=[], rationale="mastered")
    agent = _agent_with_result(result)
    out = agent.adapt(_GRAPH_JSON, "loops", 95.0, "all tests passed")
    assert out.new_nodes == []
    assert out.new_edges[0].target == "funcs"


def test_llm_failure_returns_none():
    agent = AdaptationAgent.__new__(AdaptationAgent)
    agent.structured_llm = MagicMock()
    agent.structured_llm.invoke.side_effect = RuntimeError("boom")
    agent.chat_prompt = MagicMock()
    agent.chat_prompt.format_messages.return_value = []
    assert agent.adapt(_GRAPH_JSON, "loops", 10.0, "fail") is None


def test_empty_node_id_raises():
    agent = _agent_with_result(None)
    try:
        agent.adapt(_GRAPH_JSON, "", 10.0, "x")
        assert False, "expected ValueError"
    except ValueError:
        pass
