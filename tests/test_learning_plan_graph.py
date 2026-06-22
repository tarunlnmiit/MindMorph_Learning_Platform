"""Routing + fan-in tests for the top-level MindMorph graph, all agents mocked
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
    market.extract_job_title = AsyncMock(return_value="ML Engineer")
    market.scraper.initialize = AsyncMock()
    market.scraper.search_jobs = AsyncMock(return_value="dataset123")
    market.scraper.fetch_job_results = AsyncMock(
        return_value=[{"title": "ML Engineer", "organization": "Acme"}]
    )
    market.summarize_job = AsyncMock(return_value="JOB_SUMMARY")
    return market


def _mock_consensus():
    consensus = MagicMock()
    sg = MagicMock()
    sg.model_dump.return_value = {
        "summary": "roadmap",
        "nodes": [{"id": "python_basics", "label": "Python Basics", "level": "foundational"}],
        "edges": [],
    }
    consensus.build_skill_graph.return_value = sg
    return consensus


def _mock_reviewer():
    reviewer = MagicMock()
    reviewer.review_skill_graph.return_value = MagicMock(passed=True, notes="Looks coherent.")
    return reviewer


async def test_scout_route_runs_full_learning_plan(monkeypatch):
    monkeypatch.setattr(glp, "_fetch_github_repos", AsyncMock(return_value=None))

    orchestrator = MagicMock()
    orchestrator.route_query.return_value = MagicMock(Assigned_Agent="SCOUT", Reasoning="r")
    academic = MagicMock()
    academic.provide_academic_roadmap.return_value = MagicMock(content="ACADEMIC_RESULT")
    practical = MagicMock()
    practical.provide_practical_advice.return_value = MagicMock(content="PRACTICAL_RESULT")
    consensus = _mock_consensus()
    reviewer = _mock_reviewer()

    graph = build_graph(
        orchestrator=orchestrator,
        scout=_mock_scout(),
        academic=academic,
        market=_mock_market(),
        practical=practical,
        consensus=consensus,
        reviewer=reviewer,
    )
    state = await graph.ainvoke({"user_query": "learn ML"})

    assert state["route"] == "SCOUT"
    assert state["academic_output"] == "ACADEMIC_RESULT"
    assert state["market_output"]["summary"] == "JOB_SUMMARY"
    assert state["practical_output"] == "PRACTICAL_RESULT"
    # Consensus fan-in: runs exactly ONCE after all three specialists (LangGraph superstep),
    # not once per incoming edge.
    assert consensus.build_skill_graph.call_count == 1
    # Consensus saw all three perspectives.
    consensus.build_skill_graph.assert_called_once_with(
        "learn ML", "ACADEMIC_RESULT", "JOB_SUMMARY", "PRACTICAL_RESULT"
    )
    # Reviewer runs after consensus, exactly once.
    assert reviewer.review_skill_graph.call_count == 1
    assert state["skill_graph"]["summary"] == "roadmap"
    assert "flowchart TD" in state["skill_graph_mermaid"]
    assert state["review_passed"] is True
    assert state["review_notes"] == "Looks coherent."


async def test_content_route_runs_dual_path():
    orchestrator = MagicMock()
    orchestrator.route_query.return_value = MagicMock(Assigned_Agent="CONTENT", Reasoning="r")

    content = MagicMock()
    content.generate_content.return_value = "CREATIVE_DRAFT"
    factual = MagicMock()
    factual.gather_facts.return_value = "FACTUAL_FINDINGS"
    synthesizer = MagicMock()
    synthesizer.synthesize.return_value = "FINAL_LESSON"

    graph = build_graph(
        orchestrator=orchestrator,
        content=content,
        factual=factual,
        synthesizer=synthesizer,
    )
    state = await graph.ainvoke({"user_query": "Python lists", "format_type": "B"})

    assert state["route"] == "CONTENT"
    assert state["creative_draft"] == "CREATIVE_DRAFT"
    assert state["factual_findings"] == "FACTUAL_FINDINGS"
    assert state["final_content"] == "FINAL_LESSON"
    content.generate_content.assert_called_once_with("Python lists", "B", remediation=None, context=None)
    synthesizer.synthesize.assert_called_once_with("Python lists", "CREATIVE_DRAFT", "FACTUAL_FINDINGS")


async def test_exercise_route_runs_exercise_subgraph(monkeypatch):
    # Neutralize the exercise sub-graph's live I/O: GitHub MCP + the FactualAgent (ddgs) blog/dataset
    # sources default to real network calls, which tests must not make.
    monkeypatch.setattr(glp, "_fetch_github_repos", AsyncMock(return_value=None))
    from agents.factual.factual_agent import FactualAgent
    monkeypatch.setattr(FactualAgent, "gather_facts", lambda self, query: None)

    orchestrator = MagicMock()
    orchestrator.route_query.return_value = MagicMock(Assigned_Agent="EXERCISE", Reasoning="r")
    scout = MagicMock()
    consensus = MagicMock()

    format_selector = MagicMock()
    format_selector.select_format.return_value = MagicMock(format="coding_challenge", reasoning="r")
    exercise_synthesizer = MagicMock()
    exercise_synthesizer.synthesize.return_value = "EXERCISE_STATEMENT"
    grader = MagicMock()
    artifact = MagicMock()
    artifact.model_dump.return_value = {
        "format": "coding_challenge",
        "unit_tests": ["def test_x(): assert True"],
        "rubric": [],
        "instructions": "submit",
    }
    grader.build_grading_artifact.return_value = artifact

    graph = build_graph(
        orchestrator=orchestrator,
        scout=scout,
        consensus=consensus,
        format_selector=format_selector,
        exercise_synthesizer=exercise_synthesizer,
        grader=grader,
    )
    state = await graph.ainvoke({"user_query": "give me practice"})

    assert state["route"] == "EXERCISE"
    assert state["exercise_format"] == "coding_challenge"
    assert state["exercise_statement"] == "EXERCISE_STATEMENT"
    assert state["grading_artifact"]["unit_tests"]
    scout.generate_specialized_queries.assert_not_called()
    consensus.build_skill_graph.assert_not_called()
    assert "skill_graph" not in state
