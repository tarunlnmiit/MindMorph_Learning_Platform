"use client";

import { useState } from "react";

// In-browser Python scratchpad (P3 #12) via a hosted JupyterLite REPL (WASM kernel). Exploration only —
// the official run/grade still goes through the server-side executor. Lazy: the iframe mounts only when
// the panel is opened, so it never costs the initial lesson load.
const JUPYTERLITE_URL =
  process.env.NEXT_PUBLIC_JUPYTERLITE_URL ??
  "https://jupyterlite.github.io/demo/repl/index.html?kernel=python&theme=JupyterLab%20Dark";

export function Sandbox() {
  const [open, setOpen] = useState(false);

  return (
    <div className="mt-6">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="accent-ring rounded-lg border border-white/10 px-4 py-2 text-sm text-text-muted hover:text-text"
      >
        {open ? "Hide scratchpad ▾" : "Try it live ▸"}
      </button>

      {open && (
        <div className="mt-3">
          <p className="mb-2 text-xs text-text-muted">
            In-browser Python — a scratchpad to experiment. Your graded submission still uses the editor
            above.
          </p>
          <iframe
            title="JupyterLite Python scratchpad"
            src={JUPYTERLITE_URL}
            sandbox="allow-scripts allow-same-origin"
            className="h-[480px] w-full rounded-xl border border-white/10 bg-ink-900"
            loading="lazy"
          />
        </div>
      )}
    </div>
  );
}
