// Typed client for the MindMorph FastAPI service. All calls are thin wrappers over fetch; the API
// holds no per-request state, so the whole learning_session is passed back and forth as a blob.

import type {
  IngestResponse,
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
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = body?.detail;
    if (res.status === 409) throw new LockedError(detail?.pending ?? []);
    // 503 (and friends) carry a safe string message — surface it verbatim for the UI to show.
    throw new Error(typeof detail === "string" ? detail : `Request failed (${res.status}).`);
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

  gradeAssessment(userId: string, sessionId: string, answers: number[]) {
    return req<SessionResponse>(
      `/sessions/${encodeURIComponent(userId)}/${encodeURIComponent(sessionId)}/assessment`,
      { method: "POST", body: JSON.stringify({ answers }) },
    );
  },

  // Multipart upload — must NOT set Content-Type (the browser sets the multipart boundary), so this
  // bypasses `req` (which forces application/json).
  async ingestKnowledge(userId: string, file: File): Promise<IngestResponse> {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/users/${encodeURIComponent(userId)}/knowledge`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      const detail = body?.detail;
      throw new Error(typeof detail === "string" ? detail : `Upload failed (${res.status}).`);
    }
    return res.json() as Promise<IngestResponse>;
  },
};

export type { LearningSession };
