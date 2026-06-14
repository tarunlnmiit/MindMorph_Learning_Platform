"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { LessonPanel } from "@/components/LessonPanel";
import { SkillGraph } from "@/components/SkillGraph";
import { LockedError, api } from "@/lib/api";
import { completeNodeIds, incompletePrereqLabels } from "@/lib/status";
import type { SessionResponse } from "@/lib/types";
import { useUser } from "@/lib/useUser";

export default function SessionPage() {
  const { userId, ready } = useUser();
  const router = useRouter();
  const sessionId = String(useParams().sessionId);
  const qc = useQueryClient();
  const [lockMsg, setLockMsg] = useState<string | null>(null);

  const key = ["session", userId, sessionId];

  const sessionQ = useQuery({
    queryKey: key,
    queryFn: () => api.getSession(userId!, sessionId),
    enabled: !!userId,
  });

  // Both mutations return the full, server-updated learning_session; write it straight into the
  // cache so the graph re-colors and any remedial node appears without a refetch.
  const writeBack = (res: SessionResponse) => qc.setQueryData(key, res);

  const open = useMutation({
    mutationFn: (nodeId: string) => api.openLesson(userId!, sessionId, nodeId),
    onSuccess: writeBack,
    onError: (e) => {
      if (e instanceof LockedError) setLockMsg(`Locked — first complete: ${e.pending.join(", ")}`);
    },
  });

  const grade = useMutation({
    mutationFn: ({ nodeId, solution }: { nodeId: string; solution: string }) =>
      api.grade(userId!, sessionId, nodeId, solution),
    onSuccess: writeBack,
  });

  if (ready && !userId) {
    router.push("/");
    return null;
  }
  if (sessionQ.isLoading) return <Center>Loading path…</Center>;
  if (sessionQ.isError || !sessionQ.data) return <Center>Couldn’t load this path.</Center>;

  const session = sessionQ.data.learning_session;
  const total = session.skill_graph.nodes.length;
  const complete = completeNodeIds(session.skill_graph, session.node_state).size;
  const selected = session.selected_node;

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <button onClick={() => router.push("/")} className="text-sm text-text-muted hover:text-text">
            ← All paths
          </button>
          <h1 className="mt-1 text-2xl font-semibold text-text-strong">
            {session.summary ?? "Your learning path"}
          </h1>
        </div>
        <div className="surface px-5 py-3 text-right">
          <p className="text-2xl font-semibold" style={{ color: "var(--color-mastered)" }}>
            {complete}
            <span className="text-text-muted">/{total}</span>
          </p>
          <p className="text-xs uppercase tracking-wider text-text-muted">skills complete</p>
        </div>
      </header>

      <div className="mt-8 grid gap-7 lg:grid-cols-[1.1fr_1fr]">
        <div>
          <SkillGraph
            session={session}
            onOpen={(nodeId, locked) => {
              setLockMsg(null);
              if (locked) {
                setLockMsg(
                  `Locked — first complete: ${incompletePrereqLabels(session.skill_graph, session.node_state, nodeId).join(", ")}`,
                );
                return;
              }
              open.mutate(nodeId);
            }}
          />
          {lockMsg && (
            <p className="mt-3 rounded-lg border px-4 py-2 text-sm" style={{ color: "var(--color-blocked)", borderColor: "var(--color-blocked)" }}>
              🔒 {lockMsg}
            </p>
          )}
          {open.isPending && <p className="mt-3 text-sm text-text-muted">Composing lesson…</p>}
        </div>

        <div>
          {selected && session.lessons[selected] ? (
            <LessonPanel
              session={session}
              nodeId={selected}
              grading={grade.isPending}
              onGrade={(solution) => grade.mutate({ nodeId: selected, solution })}
            />
          ) : (
            <div className="surface flex h-full min-h-[300px] items-center justify-center p-8 text-center text-text-muted">
              Pick a skill on the graph to open its lesson.
            </div>
          )}
        </div>
      </div>
    </main>
  );
}

function Center({ children }: { children: React.ReactNode }) {
  return (
    <main className="grid min-h-screen place-items-center px-6 text-text-muted">{children}</main>
  );
}
