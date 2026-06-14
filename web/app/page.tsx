"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useUser } from "@/lib/useUser";

export default function HomePage() {
  const { userId, ready, signIn, signOut } = useUser();
  if (!ready) return <Shell><div className="text-text-muted">Loading…</div></Shell>;
  if (!userId) return <LoginGate onSignIn={signIn} />;
  return <Dashboard userId={userId} onSignOut={signOut} />;
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col px-6 py-16">{children}</main>
  );
}

function LoginGate({ onSignIn }: { onSignIn: (id: string) => void }) {
  const [email, setEmail] = useState("");
  return (
    <Shell>
      <div className="flex flex-1 flex-col justify-center">
        <p className="eyebrow mb-4">Adaptive Learning</p>
        <h1 className="max-w-2xl text-5xl font-semibold leading-[1.05] text-text-strong md:text-6xl">
          Click a skill. Learn it.{" "}
          <span style={{ color: "var(--color-gold)" }}>Prove it.</span>
        </h1>
        <p className="mt-5 max-w-xl text-lg text-text-muted">
          MindMorph maps what you want to learn into a skill graph, then adapts the path to how you
          actually perform.
        </p>
        <form
          className="mt-10 flex max-w-md gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            onSignIn(email);
          }}
        >
          <input
            type="email"
            required
            placeholder="you@email.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            aria-label="Email"
            className="accent-ring flex-1 rounded-xl border border-white/10 bg-ink-800 px-4 py-3 text-text-strong placeholder:text-text-muted/60"
          />
          <button
            type="submit"
            className="accent-ring rounded-xl px-5 py-3 font-medium text-ink-900 transition-transform hover:-translate-y-0.5"
            style={{ background: "var(--color-gold)" }}
          >
            Enter
          </button>
        </form>
        <p className="mt-3 text-xs text-text-muted/70">No password — MVP identity only.</p>
      </div>
    </Shell>
  );
}

function Dashboard({ userId, onSignOut }: { userId: string; onSignOut: () => void }) {
  const router = useRouter();
  const qc = useQueryClient();
  const [query, setQuery] = useState("");

  const sessions = useQuery({
    queryKey: ["sessions", userId],
    queryFn: () => api.listSessions(userId),
  });

  const create = useMutation({
    mutationFn: () => api.createSession(userId, query),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["sessions", userId] });
      if (res.session_id) router.push(`/session/${res.session_id}`);
    },
  });

  return (
    <Shell>
      <header className="flex items-center justify-between">
        <p className="eyebrow">MindMorph</p>
        <button onClick={onSignOut} className="text-sm text-text-muted hover:text-text">
          {userId} · sign out
        </button>
      </header>

      <section className="surface mt-8 p-6">
        <h2 className="text-xl font-semibold text-text-strong">Start a new path</h2>
        <form
          className="mt-4 flex flex-col gap-3 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            if (query.trim()) create.mutate();
          }}
        >
          <input
            placeholder="e.g. Learn Python for data science"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="What do you want to learn?"
            className="accent-ring flex-1 rounded-xl border border-white/10 bg-ink-850 px-4 py-3 text-text-strong placeholder:text-text-muted/60"
          />
          <button
            type="submit"
            disabled={create.isPending}
            className="accent-ring rounded-xl px-5 py-3 font-medium text-ink-900 disabled:opacity-60"
            style={{ background: "var(--color-gold)" }}
          >
            {create.isPending ? "Building…" : "Generate"}
          </button>
        </form>
        {create.isError && (
          <p className="mt-3 text-sm" style={{ color: "var(--color-review)" }}>
            Couldn’t reach the learning service. Is the API running?
          </p>
        )}
        {create.isPending && (
          <p className="mt-3 text-sm text-text-muted">
            Orchestrating agents — this runs the full graph and can take a minute.
          </p>
        )}
      </section>

      <section className="mt-10">
        <h2 className="text-sm uppercase tracking-wider text-text-muted">Your paths</h2>
        <div className="mt-4 grid gap-3">
          {sessions.isLoading && <p className="text-text-muted">Loading…</p>}
          {sessions.data?.length === 0 && (
            <p className="text-text-muted">No paths yet — start one above.</p>
          )}
          {sessions.data?.map((s) => (
            <button
              key={s.session_id}
              onClick={() => router.push(`/session/${s.session_id}`)}
              className="surface accent-ring group flex items-center justify-between p-5 text-left transition-transform hover:-translate-y-0.5"
            >
              <span className="font-medium text-text-strong">{s.title || "Untitled path"}</span>
              <span className="text-sm text-text-muted group-hover:text-gold">Resume →</span>
            </button>
          ))}
        </div>
      </section>
    </Shell>
  );
}
