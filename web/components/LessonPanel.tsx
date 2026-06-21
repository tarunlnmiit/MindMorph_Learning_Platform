"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CodeEditor } from "./CodeEditor";
import { GradeResult } from "./GradeResult";
import { Sandbox } from "./Sandbox";
import type { LearningSession } from "@/lib/types";

export function LessonPanel({
  session,
  nodeId,
  onGrade,
  grading,
}: {
  session: LearningSession;
  nodeId: string;
  onGrade: (solution: string) => void;
  grading: boolean;
}) {
  const lesson = session.lessons[nodeId];
  const [solution, setSolution] = useState("");

  if (!lesson) return null;
  const exercise = lesson.exercise;
  const isCoding = (exercise?.format ?? "coding_challenge") === "coding_challenge";
  const lastFeedback = session.node_state[nodeId]?.last_feedback ?? null;

  return (
    <article className="surface p-7 md:p-10">
      <p className="eyebrow mb-4">Lesson</p>

      {/* The lesson markdown leads with its own <h1>, so no separate panel title (avoids duplicate). */}
      <div className="prose prose-invert prose-lg lesson-prose max-w-none">
        {lesson.content ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{lesson.content}</ReactMarkdown>
        ) : (
          <p className="text-text-muted">Lesson content could not be generated.</p>
        )}
      </div>

      {exercise?.statement && (
        <section className="mt-10 rounded-2xl border border-white/10 bg-ink-850/60 p-6 md:p-7">
          <div className="mb-4 flex items-center gap-3">
            <span
              className="h-6 w-1 rounded-full"
              style={{ background: "var(--color-progress)" }}
              aria-hidden
            />
            <p className="eyebrow" style={{ color: "var(--color-progress)" }}>
              Practice
            </p>
          </div>

          <div className="prose prose-invert lesson-prose max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{exercise.statement}</ReactMarkdown>
          </div>

          <div className="mt-6">
            {isCoding ? (
              <CodeEditor value={solution} onChange={setSolution} />
            ) : (
              <textarea
                value={solution}
                onChange={(e) => setSolution(e.target.value)}
                placeholder="Your analysis…"
                aria-label="Your analysis"
                className="accent-ring h-48 w-full rounded-xl border border-white/10 bg-ink-900 p-4 text-text-strong"
              />
            )}
          </div>

          <button
            onClick={() => onGrade(solution)}
            disabled={grading || !solution.trim()}
            className="accent-ring mt-5 rounded-xl px-6 py-2.5 font-medium text-ink-900 transition-transform hover:-translate-y-0.5 disabled:opacity-50 disabled:hover:translate-y-0"
            style={{ background: "var(--color-gold)" }}
          >
            {grading ? "Grading…" : "Grade my submission"}
          </button>

          {lastFeedback && <GradeResult result={lastFeedback} />}

          {isCoding && <Sandbox />}
        </section>
      )}
    </article>
  );
}
