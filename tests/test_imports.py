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


def test_format_selector_import_has_no_side_effects():
    out = _import_output("agents.exercise.format_selector_agent")
    assert "choosing exercise format" not in out


def test_exercise_synthesizer_import_has_no_side_effects():
    out = _import_output("agents.exercise.exercise_synthesizer_agent")
    assert "composing personalized exercise" not in out


def test_grader_import_has_no_side_effects():
    out = _import_output("agents.exercise.grader_agent")
    assert "building grading harness" not in out


def test_code_executor_import_has_no_side_effects():
    # Importing the executor must not execute any code.
    out = _import_output("tools.code_executor")
    assert "Executing" not in out


def test_graph_module_imports_clean():
    out = _import_output("graph.learning_plan_graph")
    assert "pushed to LangSmith" not in out


def test_content_graph_module_imports_clean():
    out = _import_output("graph.content_graph")
    assert "ContentAgent: Generating" not in out


def test_exercise_graph_module_imports_clean():
    out = _import_output("graph.exercise_graph")
    assert "choosing exercise format" not in out


def test_lesson_graph_module_imports_clean():
    out = _import_output("graph.lesson_graph")
    assert "ContentAgent: Generating" not in out
    assert "choosing exercise format" not in out


def test_adaptation_agent_import_has_no_side_effects():
    out = _import_output("agents.adaptation.adaptation_agent")
    assert "evaluating node" not in out  # the logged adapt() line must not fire on import


def test_skill_graph_adapt_imports_clean():
    # Pure deterministic merge module: import must not touch the LLM or print anything.
    out = _import_output("graph.skill_graph_adapt")
    assert "Adaptation:" not in out


def test_logging_config_imports_clean():
    # Importing the logging config must not configure handlers or write any log line.
    out = _import_output("logging_config")
    assert "Logging configured" not in out
