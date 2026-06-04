"""Routing + fan-out tests for the Learning-Plan graph, with all agents mocked
(no real LLM / network)."""
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)

import graph.learning_plan_graph as glp
from graph.learning_plan_graph import build_graph


def _mock_scout():
    scout = MagicMock()
    out = MagicMock()
    out.model_dump.return_value = {
        "sub_agent_queries": {"ACADEMIC": "a", "MARKET": "m", "PRACTICAL": "p"}
    }
    scout.generate_specialized_queries.return_value = out
    return scout


def _mock_market():
    market = MagicMock()
    market.scraper.initialize = AsyncMock()
    market.scraper.search_jobs = AsyncMock(return_value="dataset123")
    market.scraper.fetch_job_results = AsyncMock(
        return_value=[{"title": "ML Engineer", "organization": "Acme"}]
    )
    market.summarize_job = AsyncMock(return_value="JOB_SUMMARY")
    return market


async def test_scout_route_populates_all_three_outputs(monkeypatch):
    # No GitHub network during the test.
    monkeypatch.setattr(glp, "_fetch_github_repos", AsyncMock(return_value=None))

    orchestrator = MagicMock()
    orchestrator.route_query.return_value = MagicMock(Assigned_Agent="SCOUT", Reasoning="r")

    academic = MagicMock()
    academic.provide_academic_roadmap.return_value = MagicMock(content="ACADEMIC_RESULT")

    practical = MagicMock()
    practical.provide_practical_advice.return_value = MagicMock(content="PRACTICAL_RESULT")

    graph = build_graph(orchestrator, _mock_scout(), academic, _mock_market(), practical)
    state = await graph.ainvoke({"user_query": "learn ML"})

    assert state["route"] == "SCOUT"
    assert state["academic_output"] == "ACADEMIC_RESULT"
    assert state["market_output"]["summary"] == "JOB_SUMMARY"
    assert state["market_output"]["job"]["title"] == "ML Engineer"
    assert state["practical_output"] == "PRACTICAL_RESULT"
    # Specialists were fed their scout-decomposed queries.
    academic.provide_academic_roadmap.assert_called_once_with("a")
    practical.provide_practical_advice.assert_called_once_with("p", github_repos=None)


async def test_content_route_hits_placeholder():
    orchestrator = MagicMock()
    orchestrator.route_query.return_value = MagicMock(Assigned_Agent="CONTENT", Reasoning="r")
    scout = MagicMock()

    graph = build_graph(orchestrator, scout, MagicMock(), MagicMock(), MagicMock())
    state = await graph.ainvoke({"user_query": "write a lesson"})

    assert state["route"] == "CONTENT"
    assert "Under development" in state["placeholder"]
    # Scout / specialists never run on the non-SCOUT route.
    scout.generate_specialized_queries.assert_not_called()
    assert "academic_output" not in state
