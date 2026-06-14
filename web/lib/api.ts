// Typed client for the MindMorph FastAPI service. All calls are thin wrappers over fetch; the API
// holds no per-request state, so the whole learning_session is passed back and forth as a blob.

import type {
  LearningSession,
  SessionMeta,
  SessionResponse,
  StartSessionResponse,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class LockedError extends Error {
  pending: string[];
  constructor(pending: string[]) {
    super("Node is locked");
    this.name = "LockedError";
    this.pending = pending;
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (res.status === 409) {
    const body = await res.json().catch(() => ({}));
    throw new LockedError(body?.detail?.pending ?? []);
  }
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  createSession(userId: string, query: string, formatType = "B") {
    return req<StartSessionResponse>("/sessions", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, query, format_type: formatType }),
    });
  },

  listSessions(userId: string) {
    return req<SessionMeta[]>(`/sessions/${encodeURIComponent(userId)}`);
  },

  getSession(userId: string, sessionId: string) {
    return req<SessionResponse>(
      `/sessions/${encodeURIComponent(userId)}/${encodeURIComponent(sessionId)}`,
    );
  },

  openLesson(userId: string, sessionId: string, nodeId: string) {
    return req<SessionResponse>(
      `/sessions/${encodeURIComponent(userId)}/${encodeURIComponent(sessionId)}/lessons/${encodeURIComponent(nodeId)}`,
      { method: "POST" },
    );
  },

  grade(userId: string, sessionId: string, nodeId: string, solution: string) {
    const q = new URLSearchParams({ node_id: nodeId }).toString();
    return req<SessionResponse>(
      `/sessions/${encodeURIComponent(userId)}/${encodeURIComponent(sessionId)}/grade?${q}`,
      { method: "POST", body: JSON.stringify({ solution }) },
    );
  },
};

export type { LearningSession };
