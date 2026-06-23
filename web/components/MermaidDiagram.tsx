"use client";

import { useEffect, useId, useState } from "react";

// Renders a Mermaid diagram (the §6.3 visual-generator output). Client-only — mermaid needs the DOM.
// On a parse error it falls back to the raw code block, so a malformed diagram never breaks the lesson.
export function MermaidDiagram({ code }: { code: string }) {
  const id = useId().replace(/:/g, "");
  const [svg, setSvg] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({ startOnLoad: false, theme: "dark", securityLevel: "strict" });
        const { svg } = await mermaid.render(`mmd-${id}`, code);
        if (!cancelled) setSvg(svg);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [code, id]);

  if (failed) {
    return (
      <pre className="overflow-x-auto rounded-lg bg-ink-900 p-4 text-sm text-text-muted">
        <code>{code}</code>
      </pre>
    );
  }
  if (!svg) {
    return <p className="text-sm text-text-muted">Rendering diagram…</p>;
  }
  return (
    <div
      className="my-4 flex justify-center [&_svg]:max-w-full"
      // mermaid renders to SVG markup; securityLevel:'strict' sanitizes it before we inject.
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
