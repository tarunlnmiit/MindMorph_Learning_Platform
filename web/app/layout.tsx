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
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
