"use client";

import Editor from "@monaco-editor/react";

// Monaco editor for coding_challenge solutions (replaces Streamlit's st_ace). Returns the raw code
// string; server-side hardened-sandbox grading is unchanged.
export function CodeEditor({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-white/10">
      <Editor
        height="300px"
        defaultLanguage="python"
        theme="vs-dark"
        value={value}
        onChange={(v) => onChange(v ?? "")}
        options={{
          fontSize: 14,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          tabSize: 4,
          padding: { top: 12, bottom: 12 },
        }}
      />
    </div>
  );
}
