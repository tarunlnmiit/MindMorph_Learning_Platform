"use client";

import type { GradeResult as GradeResultT } from "@/lib/types";

// Renders a persisted grade result (node_state.last_feedback), mirroring the Streamlit grade panel.
export function GradeResult({ result }: { result: GradeResultT }) {
  // The generated tests were broken, so nothing was measured. Say that plainly — showing 0% here
  // would blame the learner for our defect.
  if (result.harness_error) {
    return (
      <div className="mt-5 rounded-xl border border-white/10 bg-ink-850 p-4">
        <p className="text-sm font-semibold" style={{ color: "var(--color-progress)" }}>
          Not graded — the exercise&apos;s auto-grading tests are broken on our side.
        </p>
        <p className="mt-2 text-sm text-text-muted">
          Your submission was not scored and your progress is unchanged. Reopen the lesson to get a
          fresh exercise.
        </p>
        {(result.failures ?? []).map((f, i) => (
          <pre key={i} className="mt-2 overflow-x-auto rounded-lg bg-ink-900 p-3 text-xs text-text-muted">
            {f}
          </pre>
        ))}
      </div>
    );
  }

  const score = Math.round(result.score ?? 0);
  const isCoding = result.passed != null && result.total != null;
  const passed = isCoding && result.passed === result.total && (result.total ?? 0) > 0;
  const tone = passed || score >= 80 ? "var(--color-mastered)" : score >= 50 ? "var(--color-progress)" : "var(--color-review)";

  return (
    <div className="mt-5 rounded-xl border border-white/10 bg-ink-850 p-4">
      <div className="flex items-baseline gap-3">
        <span className="text-2xl font-semibold" style={{ color: tone }}>
          {score}%
        </span>
        {isCoding && (
          <span className="text-sm text-text-muted">
            {result.passed}/{result.total} tests passed
          </span>
        )}
      </div>

      {result.timed_out && (
        <p className="mt-2 text-sm" style={{ color: "var(--color-progress)" }}>
          Execution timed out (possible infinite loop).
        </p>
      )}

      {(result.failures ?? []).map((f, i) => (
        <pre key={i} className="mt-2 overflow-x-auto rounded-lg bg-ink-900 p-3 text-xs text-text">
          {f}
        </pre>
      ))}

      {(result.per_criterion ?? []).map((line, i) => (
        <p key={i} className="mt-1 text-sm text-text">
          • {line}
        </p>
      ))}

      {result.feedback && <p className="mt-3 text-sm text-text">{result.feedback}</p>}
    </div>
  );
}
