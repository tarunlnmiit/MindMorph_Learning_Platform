"""Eval-runner aggregation — hermetic (fake generate + fake judge, no LLM)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from evals.runner import EvalReport, EvalRow, run_evals


class _Score:
    def __init__(self, score, grounded, feedback="ok"):
        self.score = score
        self.grounded = grounded
        self.feedback = feedback


_CASES = [{"id": "a"}, {"id": "b"}]


def _gen(case):
    return f"content for {case['id']}"


def test_mean_and_pass_above_threshold():
    report = run_evals(_CASES, _gen, lambda c, _: _Score(90, True), threshold=70)
    assert report.mean == 90.0 and report.passed is True
    assert [r.id for r in report.rows] == ["a", "b"]  # rows map 1:1 to cases


def test_fails_below_threshold():
    report = run_evals(_CASES, _gen, lambda c, _: _Score(50, False), threshold=70)
    assert report.mean == 50.0 and report.passed is False


def test_threshold_boundary_is_inclusive():
    report = run_evals([{"id": "x"}], _gen, lambda c, _: _Score(70, True), threshold=70)
    assert report.passed is True


def test_none_judge_result_scores_zero():
    report = run_evals(_CASES, _gen, lambda c, _: (None if c["id"] == "a" else _Score(100, True)), 70)
    a = next(r for r in report.rows if r.id == "a")
    assert a.score == 0.0 and a.grounded is False
    assert report.mean == 50.0 and report.passed is False


def test_generate_output_reaches_judge():
    seen = {}

    def judge(case, content):
        seen[case["id"]] = content
        return _Score(80, True)

    run_evals([{"id": "z"}], _gen, judge, 70)
    assert seen["z"] == "content for z"


def test_empty_report_does_not_pass():
    assert EvalReport(rows=[], threshold=70).passed is False


def test_render_contains_verdict():
    report = EvalReport(rows=[EvalRow("a", 90, True, "clean")], threshold=70)
    out = report.render()
    assert "PASS" in out and "mean 90.0" in out
