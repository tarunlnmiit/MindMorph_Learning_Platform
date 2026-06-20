"""Service-layer orchestration (Streamlit-free): session construction, lesson open + lock gate, and
grade → mastery → adapt. LLM/graph calls are monkeypatched so these stay fast, deterministic unit
tests. The mastery/completion math itself is covered by test_mastery_capture / test_completion_gating."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)

import pytest

from services import learning_service as svc


def _scout_state():
    return {
        "route": "SCOUT",
        "skill_graph": {
            "summary": "Path",
            "nodes": [
                {"id": "a", "label": "A", "description": "first", "level": "foundational"},
                {"id": "b", "label": "B", "description": "second", "level": "intermediate"},
            ],
            "edges": [{"source": "a", "target": "b", "relation": "prerequisite"}],
        },
        "format_type": "B",
    }


def test_new_learning_session_builds_available_node_state():
    ls = svc.new_learning_session(_scout_state(), "B")
    assert ls is not None
    assert set(ls["node_state"]) == {"a", "b"}
    assert all(s["status"] == "available" for s in ls["node_state"].values())
    assert ls["lessons"] == {}
    assert ls["selected_node"] is None


def test_new_learning_session_none_without_nodes():
    assert svc.new_learning_session({"skill_graph": {"nodes": []}}, "B") is None
    assert svc.new_learning_session({}, "B") is None


def test_open_lesson_blocks_locked_node(monkeypatch):
    monkeypatch.setattr(svc, "_run_lesson", lambda *a, **k: {"content": "x"})
    ls = svc.new_learning_session(_scout_state(), "B")
    # 'b' depends on 'a'; 'a' not mastered ⇒ 'b' locked.
    with pytest.raises(svc.LockedNodeError) as ei:
        svc.open_lesson(ls, "b")
    assert "A" in ei.value.pending


def test_open_lesson_composes_and_caches(monkeypatch):
    calls = {"n": 0}

    def fake_run_lesson(node, fmt, weak, user_id=None):
        calls["n"] += 1
        return {
            "content": f"lesson for {node['id']}",
            "exercise_format": "coding_challenge",
            "exercise_statement": "do it",
            "grading_artifact": {"format": "coding_challenge", "unit_tests": []},
        }

    monkeypatch.setattr(svc, "_run_lesson", fake_run_lesson)
    ls = svc.new_learning_session(_scout_state(), "B")
    svc.open_lesson(ls, "a")  # root node, unlocked
    assert ls["selected_node"] == "a"
    assert ls["lessons"]["a"]["content"] == "lesson for a"
    svc.open_lesson(ls, "a")  # re-open reuses cache, no second compose
    assert calls["n"] == 1


def test_grade_applies_mastery_and_runs_adaptation(monkeypatch):
    monkeypatch.setattr(svc, "_run_lesson", lambda *a, **k: {
        "content": "c", "exercise_format": "coding_challenge",
        "exercise_statement": "s", "grading_artifact": {"format": "coding_challenge", "unit_tests": []},
    })
    # Grade returns a perfect score; adaptation is stubbed (cover the wiring, not the LLM).
    import agents.exercise.grader_agent as grader
    monkeypatch.setattr(grader, "grade_submission", lambda fmt, sol, art: {"score": 100, "passed": 1, "total": 1})
    adapt_calls = {"n": 0}
    monkeypatch.setattr(svc, "adapt_after_grade", lambda ls, nid: adapt_calls.__setitem__("n", adapt_calls["n"] + 1))

    ls = svc.new_learning_session(_scout_state(), "B")
    svc.open_lesson(ls, "a")
    svc.grade(ls, "a", "solution code")
    assert ls["node_state"]["a"]["status"] == "mastered"
    assert ls["node_state"]["a"]["best_score"] == 100
    assert adapt_calls["n"] == 1


def test_grade_without_open_lesson_raises():
    ls = svc.new_learning_session(_scout_state(), "B")
    with pytest.raises(ValueError):
        svc.grade(ls, "a", "code")


# --- threshold gating + deterministic remediation lock -----------------------------------------

class _FakeAgent:
    """Records adapt() calls and returns a canned result."""
    def __init__(self, result=None):
        self.result = result
        self.calls = 0

    def adapt(self, *args, **kwargs):
        self.calls += 1
        return self.result


def _opened(monkeypatch, score):
    """Build a session with node 'a' opened and grading stubbed to a fixed score."""
    monkeypatch.setattr(svc, "_run_lesson", lambda *a, **k: {
        "content": "c", "exercise_format": "coding_challenge",
        "exercise_statement": "s", "grading_artifact": {"format": "coding_challenge", "unit_tests": []},
    })
    import agents.exercise.grader_agent as grader
    monkeypatch.setattr(grader, "grade_submission", lambda fmt, sol, art: {"score": score})
    ls = svc.new_learning_session(_scout_state(), "B")
    svc.open_lesson(ls, "a")
    return ls


def test_grade_40_79_skips_adaptation(monkeypatch):
    agent = _FakeAgent(result=None)
    monkeypatch.setattr(svc, "_get_adaptation_agent", lambda: agent)
    ls = _opened(monkeypatch, 55)
    svc.grade(ls, "a", "sol")
    assert ls["node_state"]["a"]["status"] == "in_progress"
    assert agent.calls == 0  # 40–79 band makes NO adaptation call
    assert ls["node_state"]["a"]["remediation_pending"] is False


def test_grade_sub40_locks_even_when_adapt_returns_none(monkeypatch):
    from services.completion import locked_node_ids

    agent = _FakeAgent(result=None)  # LLM "fails" — no remedial nodes
    monkeypatch.setattr(svc, "_get_adaptation_agent", lambda: agent)
    ls = _opened(monkeypatch, 20)
    svc.grade(ls, "a", "sol")
    assert ls["node_state"]["a"]["status"] == "needs_review"
    assert ls["node_state"]["a"]["remediation_pending"] is True
    assert agent.calls >= 1  # attempted (with bounded retry)
    assert "a" in locked_node_ids(ls["skill_graph"], ls["node_state"])  # locked despite None


def test_grade_sub40_adds_remedial_prereq_and_locks(monkeypatch):
    from agents.adaptation.adaptation_schema import GraphAdaptation
    from agents.consensus.skill_graph_schema import SkillEdge, SkillNode
    from services.completion import locked_node_ids

    adaptation = GraphAdaptation(
        new_nodes=[SkillNode(id="a_basics", label="A Basics", description="foundations", level="foundational")],
        new_edges=[SkillEdge(source="a_basics", target="a", relation="prerequisite")],
        remediation_focus=["foundations"],
        rationale="break it down",
    )
    monkeypatch.setattr(svc, "_get_adaptation_agent", lambda: _FakeAgent(result=adaptation))
    ls = _opened(monkeypatch, 20)
    svc.grade(ls, "a", "sol")
    assert "a_basics" in ls["node_state"]            # remedial prereq seeded
    assert "a" in locked_node_ids(ls["skill_graph"], ls["node_state"])  # locked behind new prereq
    assert "a" not in ls["lessons"]                  # cached lesson invalidated for regeneration
