"""Guard: importing an agent module must not fire LLM calls or LangSmith pushes.

Regression test for the old behaviour where orchestrator_agent.py / scout_agent.py
executed example calls at module top level (orchestrator even pushed to LangSmith).
Each module is imported in a fresh subprocess so output is not masked by import caching.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _import_output(module: str) -> str:
    res = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"import {module} failed:\n{res.stderr}"
    return res.stdout + res.stderr


def test_orchestrator_import_has_no_side_effects():
    out = _import_output("agents.orchestrator.orchestrator_agent")
    assert "pushed to LangSmith" not in out
    assert "Assigned_Agent" not in out  # the printed example response


def test_scout_import_has_no_side_effects():
    out = _import_output("agents.scout.scout_agent")
    assert "Generating specialized queries" not in out


def test_academic_import_has_no_side_effects():
    out = _import_output("agents.academic.academic_agent")
    assert "Generating academic roadmap" not in out


def test_consensus_import_has_no_side_effects():
    out = _import_output("agents.consensus.consensus_agent")
    assert "building skill dependency graph" not in out


def test_reviewer_import_has_no_side_effects():
    out = _import_output("agents.reviewer.reviewer_agent")
    assert "evaluating skill dependency graph" not in out


def test_content_agent_import_has_no_side_effects():
    out = _import_output("agents.content_generator.content_agent")
    assert "ContentAgent: Generating" not in out
    assert "=" * 50 not in out  # the old printed lesson banner


def test_factual_import_has_no_side_effects():
    out = _import_output("agents.factual.factual_agent")
    assert "searching the web" not in out


def test_synthesizer_import_has_no_side_effects():
    out = _import_output("agents.synthesizer.synthesizer_agent")
    assert "merging creative draft" not in out


def test_graph_module_imports_clean():
    out = _import_output("graph.learning_plan_graph")
    assert "pushed to LangSmith" not in out


def test_content_graph_module_imports_clean():
    out = _import_output("graph.content_graph")
    assert "ContentAgent: Generating" not in out
