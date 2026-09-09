"""Deterministic repair of an incoherent Consensus skill graph (dangling edges).

Reconstructs the real failing payload: the model emitted edges sourced from ``mlops_tools``, a node
id absent from the node list, which permanently locked ``production_ml_systems`` and
``model_deployment_and_monitoring`` and made ``is_session_complete`` unreachable. All hermetic —
no LLM, no network.
"""
import os
import sys
from unittest.mock import AsyncMock, MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)

import graph.learning_plan_graph as glp
from graph.learning_plan_graph import build_graph
from graph.skill_graph_adapt import prune_dangling_edges
from services.completion import complete_node_ids, is_session_complete, locked_node_ids


def _incoherent_graph() -> dict:
    """The live failure: `mlops_tools` is referenced by edges but is not a node."""
    return {
        "summary": "ML engineering roadmap",
        "nodes": [
            {"id": "python_basics", "label": "Python Basics", "level": "foundational"},
            {"id": "ml_fundamentals", "label": "ML Fundamentals", "level": "intermediate"},
            {"id": "production_ml_systems", "label": "Production ML Systems", "level": "advanced"},
            {"id": "model_deployment_and_monitoring",
             "label": "Model Deployment and Monitoring", "level": "advanced"},
        ],
        "edges": [
            {"source": "python_basics", "target": "ml_fundamentals", "relation": "prerequisite"},
            {"source": "ml_fundamentals", "target": "production_ml_systems", "relation": "prerequisite"},
            # Hallucinated endpoint — source side is the damaging one (prereqs_by_node keys on target).
            {"source": "mlops_tools", "target": "production_ml_systems", "relation": "prerequisite"},
            {"source": "mlops_tools", "target": "model_deployment_and_monitoring",
             "relation": "prerequisite"},
            # Target side: silently ignored by completion, but still renders a phantom mermaid box.
            {"source": "ml_fundamentals", "target": "mlops_tools", "relation": "prerequisite"},
        ],
    }


def _all_mastered(graph: dict) -> dict:
    return {n["id"]: {"status": "mastered", "best_score": 100} for n in graph["nodes"]}


def test_dangling_edges_break_completion_before_repair():
    """Guards the premise: without the repair the path is permanently unfinishable."""
    bad = _incoherent_graph()
    state = _all_mastered(bad)
    assert "production_ml_systems" in locked_node_ids(bad, state)
    assert "model_deployment_and_monitoring" in locked_node_ids(bad, state)
    assert is_session_complete(bad, state) is False


def test_prune_drops_only_dangling_edges_and_is_immutable():
    bad = _incoherent_graph()
    original_edges = [dict(e) for e in bad["edges"]]

    repaired, dropped = prune_dangling_edges(bad)

    assert bad["edges"] == original_edges  # input untouched
    assert len(dropped) == 3
    assert all("mlops_tools" in (e["source"], e["target"]) for e in dropped)
    assert repaired["nodes"] == bad["nodes"]
    assert repaired["summary"] == bad["summary"]

    node_ids = {n["id"] for n in repaired["nodes"]}
    assert all(e["source"] in node_ids and e["target"] in node_ids for e in repaired["edges"])
    # The good edges survive in order.
    assert repaired["edges"] == [original_edges[0], original_edges[1]]


def test_prune_is_a_noop_on_a_coherent_graph():
    repaired, dropped = prune_dangling_edges(_incoherent_graph() | {"edges": []})
    assert dropped == []
    assert repaired["edges"] == []


def test_node_whose_only_prereq_was_dangling_becomes_reachable():
    """Asserted through the real consumers (locked_node_ids / complete_node_ids), not the edge list."""
    repaired, _ = prune_dangling_edges(_incoherent_graph())
    fresh = {n["id"]: {"status": "available", "best_score": 0} for n in repaired["nodes"]}

    # model_deployment_and_monitoring's ONLY prerequisite was the phantom: it is now a root.
    assert "model_deployment_and_monitoring" not in locked_node_ids(repaired, fresh)
    # production_ml_systems keeps its real prerequisite chain — still locked while unmastered.
    assert "production_ml_systems" in locked_node_ids(repaired, fresh)


def test_is_session_complete_can_fire_on_a_repaired_graph():
    repaired, _ = prune_dangling_edges(_incoherent_graph())
    state = _all_mastered(repaired)
    assert locked_node_ids(repaired, state) == set()
    assert complete_node_ids(repaired, state) == {n["id"] for n in repaired["nodes"]}
    assert is_session_complete(repaired, state) is True


async def test_consensus_node_drops_dangling_edges_at_build(monkeypatch, caplog):
    """End-to-end through the compiled graph: the persisted skill_graph is already repaired."""
    monkeypatch.setattr(glp, "_fetch_github_repos", AsyncMock(return_value=None))

    orchestrator = MagicMock()
    orchestrator.route_query.return_value = MagicMock(Assigned_Agent="SCOUT", Reasoning="r")
    scout = MagicMock()
    scout_out = MagicMock()
    scout_out.model_dump.return_value = {
        "sub_agent_queries": {"ACADEMIC": "a", "MARKET": "m", "PRACTICAL": "p"}
    }
    scout.generate_specialized_queries.return_value = scout_out
    academic = MagicMock()
    academic.provide_academic_roadmap.return_value = MagicMock(content="A")
    practical = MagicMock()
    practical.provide_practical_advice.return_value = MagicMock(content="P")
    market = MagicMock()
    market.extract_job_title = AsyncMock(return_value="ML Engineer")
    market.scraper.initialize = AsyncMock()
    market.scraper.search_jobs = AsyncMock(return_value="ds1")
    market.scraper.fetch_job_results = AsyncMock(return_value=[{"title": "ML Engineer"}])
    market.summarize_job = AsyncMock(return_value="JOB")
    consensus = MagicMock()
    sg = MagicMock()
    sg.model_dump.return_value = _incoherent_graph()
    consensus.build_skill_graph.return_value = sg
    reviewer = MagicMock()
    reviewer.review_skill_graph.return_value = MagicMock(passed=True, notes="ok")

    compiled = build_graph(
        orchestrator=orchestrator, scout=scout, academic=academic, market=market,
        practical=practical, consensus=consensus, reviewer=reviewer,
    )
    with caplog.at_level("WARNING"):
        state = await compiled.ainvoke({"user_query": "learn ML engineering"})

    node_ids = {n["id"] for n in state["skill_graph"]["nodes"]}
    assert "mlops_tools" not in node_ids
    assert all(
        e["source"] in node_ids and e["target"] in node_ids
        for e in state["skill_graph"]["edges"]
    )
    # Loud, not silent.
    assert any("mlops_tools" in r.getMessage() for r in caplog.records)
    # The Reviewer receives the REPAIRED graph, so this class of incoherence never reaches it.
    assert "mlops_tools" not in reviewer.review_skill_graph.call_args[0][1]
    # ...and the phantom no longer renders.
    assert "mlops_tools" not in state["skill_graph_mermaid"]


async def test_reviewer_rejection_is_logged_loudly(monkeypatch, caplog):
    """review_passed:False is inert downstream — at minimum it must be visible in the logs."""
    monkeypatch.setattr(glp, "_fetch_github_repos", AsyncMock(return_value=None))

    orchestrator = MagicMock()
    orchestrator.route_query.return_value = MagicMock(Assigned_Agent="SCOUT", Reasoning="r")
    scout = MagicMock()
    scout_out = MagicMock()
    scout_out.model_dump.return_value = {"sub_agent_queries": {}}
    scout.generate_specialized_queries.return_value = scout_out
    academic = MagicMock()
    academic.provide_academic_roadmap.return_value = MagicMock(content="A")
    practical = MagicMock()
    practical.provide_practical_advice.return_value = MagicMock(content="P")
    market = MagicMock()
    market.extract_job_title = AsyncMock(return_value="X")
    market.scraper.initialize = AsyncMock()
    market.scraper.search_jobs = AsyncMock(return_value=None)
    consensus = MagicMock()
    sg = MagicMock()
    sg.model_dump.return_value = _incoherent_graph() | {"edges": []}
    consensus.build_skill_graph.return_value = sg
    reviewer = MagicMock()
    reviewer.review_skill_graph.return_value = MagicMock(passed=False, notes="Not coherent.")

    compiled = build_graph(
        orchestrator=orchestrator, scout=scout, academic=academic, market=market,
        practical=practical, consensus=consensus, reviewer=reviewer,
    )
    with caplog.at_level("WARNING"):
        state = await compiled.ainvoke({"user_query": "learn X"})

    assert state["review_passed"] is False
    assert any("Reviewer REJECTED" in r.getMessage() for r in caplog.records)
