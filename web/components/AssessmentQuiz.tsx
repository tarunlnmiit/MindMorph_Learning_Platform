"use client";

import { useState } from "react";
import type { AssessmentQuiz as Quiz } from "@/lib/types";

interface AssessmentQuizProps {
  quiz: Quiz;
  submitting: boolean;
  onSubmit: (answers: number[]) => void;
  onSkip: () => void;
}

// Onboarding diagnostic (P2 #8): answer to test out of skills you already know. Correct answers
// pre-seed mastered nodes on the graph.
export function AssessmentQuiz({ quiz, submitting, onSubmit, onSkip }: AssessmentQuizProps) {
  const [answers, setAnswers] = useState<number[]>(() => quiz.questions.map(() => -1));

  const choose = (qi: number, oi: number) =>
    setAnswers((prev) => prev.map((a, i) => (i === qi ? oi : a)));

  return (
    <section className="surface p-6 md:p-8">
      <p className="eyebrow mb-2">Quick check</p>
      <h2 className="text-2xl font-semibold text-text-strong">Let&rsquo;s skip what you already know</h2>
      <p className="mt-2 max-w-2xl text-sm text-text-muted">
        Answer what you can — correct answers mark those skills mastered so you start where it matters.
        Skip anything you&rsquo;re unsure about.
      </p>

      <ol className="mt-6 flex flex-col gap-6">
        {quiz.questions.map((q, qi) => (
          <li key={qi} className="rounded-xl border border-white/10 bg-ink-850 p-5">
            <p className="font-medium text-text-strong">
              <span className="text-text-muted">{qi + 1}.</span> {q.question}
            </p>
            <div className="mt-3 grid gap-2">
              {q.options.map((opt, oi) => {
                const active = answers[qi] === oi;
                return (
                  <button
                    key={oi}
                    type="button"
                    onClick={() => choose(qi, oi)}
                    aria-pressed={active}
                    className="accent-ring rounded-lg border px-4 py-2.5 text-left text-sm transition-colors"
                    style={{
                      borderColor: active ? "var(--color-gold)" : "rgba(255,255,255,0.1)",
                      color: active ? "var(--color-gold)" : "var(--color-text)",
                    }}
                  >
                    {opt}
                  </button>
                );
              })}
            </div>
          </li>
        ))}
      </ol>

      <div className="mt-6 flex items-center gap-3">
        <button
          type="button"
          disabled={submitting}
          onClick={() => onSubmit(answers)}
          className="accent-ring rounded-xl px-5 py-3 font-medium text-ink-900 disabled:opacity-60"
          style={{ background: "var(--color-gold)" }}
        >
          {submitting ? "Scoring…" : "Submit answers"}
        </button>
        <button
          type="button"
          disabled={submitting}
          onClick={onSkip}
          className="text-sm text-text-muted hover:text-text disabled:opacity-60"
        >
          Skip for now
        </button>
      </div>
    </section>
  );
}
