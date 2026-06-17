import type { Metadata } from "next";
import "./globals.css";
import "@xyflow/react/dist/style.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "MindMorph — Adaptive Learning",
  description: "Click a skill, learn it, prove it. The graph adapts to you.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // suppressHydrationWarning: browser extensions (Grammarly, VS Code, etc.) inject attributes onto
    // <html>/<body> before React hydrates, causing a benign attribute mismatch. Scoped to these two
    // elements only — it does not suppress warnings for any child content.
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
