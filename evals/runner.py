"""Pure eval aggregation — no I/O, no LLM. Unit-testable with fakes.

``run_evals`` drives generation + judging via injected callables and rolls the per-case scores into a
report with a pass/fail verdict against a threshold.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class EvalRow:
    id: str
    score: float
    grounded: bool
    feedback: str


@dataclass
class EvalReport:
    rows: list[EvalRow] = field(default_factory=list)
    threshold: float = 70.0

    @property
    def mean(self) -> float:
        return sum(r.score for r in self.rows) / len(self.rows) if self.rows else 0.0

    @property
    def passed(self) -> bool:
        return bool(self.rows) and self.mean >= self.threshold

    def render(self) -> str:
        lines = ["Groundedness eval", "=" * 40]
        for r in self.rows:
            mark = "PASS" if r.grounded else "FAIL"
            lines.append(f"[{mark}] {r.id:<24} {r.score:5.1f}  {r.feedback[:70]}")
        verdict = "PASS" if self.passed else "FAIL"
        lines += ["-" * 40, f"mean {self.mean:.1f} / threshold {self.threshold:.0f} → {verdict}"]
        return "\n".join(lines)


def run_evals(
    cases: list[dict],
    generate: Callable[[dict], str],
    judge: Callable[[dict, str], Optional[object]],
    threshold: float = 70.0,
) -> EvalReport:
    """For each case: generate content, judge it, collect a row. A None/failed judge result scores 0."""
    report = EvalReport(threshold=threshold)
    for case in cases:
        content = generate(case)
        result = judge(case, content)
        if result is None:
            report.rows.append(EvalRow(case["id"], 0.0, False, "judge failed / no result"))
            continue
        report.rows.append(
            EvalRow(case["id"], float(result.score), bool(result.grounded), result.feedback)
        )
    return report
