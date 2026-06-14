"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CodeEditor } from "./CodeEditor";
import { GradeResult } from "./GradeResult";
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
  const node = session.skill_graph.nodes.find((n) => n.id === nodeId);
  const lesson = session.lessons[nodeId];
  const [solution, setSolution] = useState("");

  if (!lesson) return null;
  const exercise = lesson.exercise;
  const isCoding = (exercise?.format ?? "coding_challenge") === "coding_challenge";
  const lastFeedback = session.node_state[nodeId]?.last_feedback ?? null;

  return (
    <article className="surface p-7">
      <p className="eyebrow">Lesson</p>
      <h2 className="mt-2 text-2xl font-semibold text-text-strong">{node?.label}</h2>

      <div className="prose-invert mt-5 max-w-none text-text [&_a]:text-gold [&_code]:text-gold [&_h1]:text-text-strong [&_h2]:text-text-strong [&_h3]:text-text-strong [&_strong]:text-text-strong">
        {lesson.content ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{lesson.content}</ReactMarkdown>
        ) : (
          <p className="text-text-muted">Lesson content could not be generated.</p>
        )}
      </div>

      {exercise?.statement && (
        <section className="mt-8 border-t border-white/10 pt-6">
          <p className="eyebrow" style={{ color: "var(--color-progress)" }}>
            Practice
          </p>
          <div className="prose-invert mt-3 max-w-none text-text">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{exercise.statement}</ReactMarkdown>
          </div>

          <div className="mt-5">
            {isCoding ? (
              <CodeEditor value={solution} onChange={setSolution} />
            ) : (
              <textarea
                value={solution}
                onChange={(e) => setSolution(e.target.value)}
                placeholder="Your analysis…"
                aria-label="Your analysis"
                className="accent-ring h-48 w-full rounded-xl border border-white/10 bg-ink-850 p-4 text-text-strong"
              />
            )}
          </div>

          <button
            onClick={() => onGrade(solution)}
            disabled={grading || !solution.trim()}
            className="accent-ring mt-4 rounded-xl px-5 py-2.5 font-medium text-ink-900 disabled:opacity-50"
            style={{ background: "var(--color-gold)" }}
          >
            {grading ? "Grading…" : "Grade my submission"}
          </button>

          {lastFeedback && <GradeResult result={lastFeedback} />}
        </section>
      )}
    </article>
  );
}
