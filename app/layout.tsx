import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Portfolio Analyst Agent — Claude sub-agent POC",
  description:
    "A lead orchestrator (Claude Sonnet 4.6) dispatches to three specialist sub-agents (Claude Haiku 4.5) via tool-use, then synthesizes their briefings into an analyst memo. Backed by an eval harness and prompt caching.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full bg-[#0a0a0f] text-white">{children}</body>
    </html>
  );
}
