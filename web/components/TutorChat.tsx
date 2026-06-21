"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";

interface TutorChatProps {
  userId: string;
  sessionId: string;
  nodeId: string | null;
  history: ChatMessage[];
  sessionKey: unknown[]; // TanStack query key to invalidate after a turn persists
}

// AI Teaching Assistant (P3 #10): grounded, streaming chat about the open lesson + the learner's material.
export function TutorChat({ userId, sessionId, nodeId, history, sessionKey }: TutorChatProps) {
  const qc = useQueryClient();
  const [input, setInput] = useState("");
  const [pendingUser, setPendingUser] = useState<string | null>(null);
  const [streaming, setStreaming] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const send = async () => {
    const message = input.trim();
    if (!message || busy) return;
    setInput("");
    setError(null);
    setPendingUser(message);
    setStreaming("");
    setBusy(true);

    await api.streamChat(userId, sessionId, nodeId, message, {
      onToken: (t) => setStreaming((s) => s + t),
      onError: (m) => {
        setError(m);
        setBusy(false);
        setPendingUser(null);
        setStreaming("");
      },
      onDone: () => {
        setBusy(false);
        setPendingUser(null);
        setStreaming("");
        // Persisted history is authoritative — refetch the session.
        qc.invalidateQueries({ queryKey: sessionKey });
      },
    });
  };

  const bubbles: ChatMessage[] = [...history];
  if (pendingUser) bubbles.push({ role: "user", content: pendingUser });

  return (
    <section className="surface p-6">
      <h2 className="text-lg font-semibold text-text-strong">Ask the teaching assistant</h2>
      <p className="mt-1 text-xs text-text-muted">
        Grounded in this lesson and your uploaded material.
      </p>

      <div className="mt-4 flex max-h-[420px] flex-col gap-3 overflow-y-auto">
        {bubbles.length === 0 && !streaming && (
          <p className="text-sm text-text-muted">No questions yet — ask anything about this skill.</p>
        )}
        {bubbles.map((m, i) => (
          <Bubble key={i} role={m.role} content={m.content} />
        ))}
        {streaming && <Bubble role="assistant" content={streaming} />}
        {busy && !streaming && <p className="text-sm text-text-muted">Thinking…</p>}
      </div>

      {error && (
        <p className="mt-3 text-sm" style={{ color: "var(--color-review)" }}>
          ⚠️ {error}
        </p>
      )}

      <form
        className="mt-4 flex gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={busy}
          placeholder="e.g. Can you explain this with an example?"
          aria-label="Message the teaching assistant"
          className="accent-ring flex-1 rounded-xl border border-white/10 bg-ink-850 px-4 py-3 text-text-strong placeholder:text-text-muted/60 disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="accent-ring rounded-xl px-5 py-3 font-medium text-ink-900 disabled:opacity-50"
          style={{ background: "var(--color-gold)" }}
        >
          Send
        </button>
      </form>
    </section>
  );
}

function Bubble({ role, content }: { role: "user" | "assistant"; content: string }) {
  const isUser = role === "user";
  return (
    <div className={isUser ? "flex justify-end" : "flex justify-start"}>
      <div
        className="max-w-[85%] whitespace-pre-wrap rounded-xl px-4 py-2.5 text-sm"
        style={{
          background: isUser ? "var(--color-gold)" : "var(--color-ink-850, rgba(255,255,255,0.05))",
          color: isUser ? "var(--color-ink-900, #0b0b0c)" : "var(--color-text)",
          border: isUser ? "none" : "1px solid rgba(255,255,255,0.1)",
        }}
      >
        {content}
      </div>
    </div>
  );
}
