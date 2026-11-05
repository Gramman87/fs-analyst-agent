"use client";

import { useState } from "react";
import { Loader2, Send, Wrench, Brain, FileText } from "lucide-react";

type Trace =
  | { kind: "thinking"; text: string }
  | { kind: "tool_call"; name: string; input: Record<string, unknown> }
  | { kind: "tool_result"; name: string; text: string }
  | { kind: "tool_error"; name: string; text: string };

type Usage = {
  input_tokens?: number;
  output_tokens?: number;
  cache_creation_input_tokens?: number;
  cache_read_input_tokens?: number;
  lead_calls?: number;
  subagent_calls?: number;
};

type Result = {
  memo: string;
  trace: Trace[];
  usage: Usage;
  engine: "claude" | "demo";
  notice: string | null;
};

const PRESETS: { name: string; query: string; holdings: Record<string, number> }[] = [
  {
    name: "Tech-heavy growth",
    query:
      "I'm overweight tech going into the next Fed meeting. Should I be worried, and what's the biggest single-name risk in this book?",
    holdings: { AAPL: 0.3, MSFT: 0.3, NVDA: 0.3, JPM: 0.05, XOM: 0.05 },
  },
  {
    name: "Balanced 60/30/10",
    query:
      "Walk me through what's moving this portfolio right now and where the asymmetry sits: what's most likely to surprise me on the upside vs. the downside?",
    holdings: { MSFT: 0.25, AAPL: 0.2, NVDA: 0.15, JPM: 0.3, XOM: 0.1 },
  },
  {
    name: "Value tilt",
    query:
      "I built this for a rate-cut cycle with a value tilt. Does the current setup support that thesis or am I wrong?",
    holdings: { JPM: 0.5, XOM: 0.3, AAPL: 0.1, MSFT: 0.1 },
  },
];

export default function Home() {
  const [query, setQuery] = useState(PRESETS[0].query);
  const [holdingsJson, setHoldingsJson] = useState(
    JSON.stringify(PRESETS[0].holdings, null, 2),
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);

  function applyPreset(idx: number) {
    setQuery(PRESETS[idx].query);
    setHoldingsJson(JSON.stringify(PRESETS[idx].holdings, null, 2));
    setError(null);
    setResult(null);
  }

  async function submit() {
    setError(null);
    setResult(null);
    let holdings: Record<string, number>;
    try {
      holdings = JSON.parse(holdingsJson);
    } catch {
      setError("Holdings must be valid JSON (ticker → weight).");
      return;
    }
    const total = Object.values(holdings).reduce((a, b) => a + Number(b), 0);
    if (Math.abs(total - 1) > 0.02) {
      setError(`Weights sum to ${total.toFixed(2)}, not ~1.0. Normalize first.`);
      return;
    }
    setLoading(true);
    try {
      const resp = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, holdings }),
      });
      const body = await resp.json();
      if (!resp.ok) throw new Error(body.error || `HTTP ${resp.status}`);
      setResult(body);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="max-w-6xl mx-auto px-6 py-12">
      {/* Header */}
      <header className="mb-12">
        <p className="text-xs font-semibold tracking-[0.3em] text-violet-400 uppercase mb-3">
          Claude Sub-Agent POC · Financial Services
        </p>
        <h1 className="text-4xl md:text-5xl font-black tracking-tight mb-4">
          Portfolio{" "}
          <span className="bg-gradient-to-r from-violet-400 via-fuchsia-400 to-cyan-400 bg-clip-text text-transparent">
            Analyst Agent
          </span>
        </h1>
        <p className="text-gray-400 max-w-2xl leading-relaxed">
          A lead orchestrator (Claude Sonnet 4.6, adaptive thinking) dispatches to three specialist
          sub-agents (Claude Haiku 4.5) through tool use, covering market data, news sentiment, and
          risk concentration, then synthesizes their briefings into a decision-grade memo. All
          data is fictional.
        </p>
      </header>

      <div className="grid lg:grid-cols-2 gap-8">
        {/* Input column */}
        <section>
          <div className="mb-6">
            <p className="text-xs font-semibold tracking-widest text-gray-500 uppercase mb-3">
              Presets
            </p>
            <div className="flex flex-wrap gap-2">
              {PRESETS.map((p, i) => (
                <button
                  key={p.name}
                  onClick={() => applyPreset(i)}
                  className="text-xs font-semibold border border-white/10 hover:border-violet-500/50 text-gray-400 hover:text-white px-3 py-1.5 rounded-full transition-colors"
                >
                  {p.name}
                </button>
              ))}
            </div>
          </div>

          <label className="block text-xs font-semibold tracking-widest text-gray-500 uppercase mb-2">
            Portfolio (ticker → weight, must sum to 1.0)
          </label>
          <textarea
            value={holdingsJson}
            onChange={(e) => setHoldingsJson(e.target.value)}
            rows={7}
            spellCheck={false}
            className="w-full bg-white/[0.03] border border-white/[0.08] rounded-xl px-4 py-3 text-sm font-mono text-gray-200 focus:outline-none focus:border-violet-500/50 mb-6"
          />

          <label className="block text-xs font-semibold tracking-widest text-gray-500 uppercase mb-2">
            Client question
          </label>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            rows={4}
            className="w-full bg-white/[0.03] border border-white/[0.08] rounded-xl px-4 py-3 text-sm text-gray-200 focus:outline-none focus:border-violet-500/50 mb-6"
          />

          <button
            onClick={submit}
            disabled={loading}
            className="w-full bg-violet-600 hover:bg-violet-500 disabled:bg-violet-900 disabled:text-gray-400 text-white font-semibold px-6 py-3 rounded-full transition-colors text-sm flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Analyzing…
              </>
            ) : (
              <>
                <Send className="w-4 h-4" /> Generate memo
              </>
            )}
          </button>

          {error && (
            <div className="mt-4 text-sm text-rose-400 border border-rose-500/30 bg-rose-500/[0.05] rounded-xl px-4 py-3">
              {error}
            </div>
          )}

          <p className="text-xs text-gray-600 mt-6">
            Coverage: AAPL · MSFT · NVDA · JPM · XOM (mock data, not market advice)
          </p>
        </section>

        {/* Output column */}
        <section>
          <p className="text-xs font-semibold tracking-widest text-gray-500 uppercase mb-3">
            Analyst memo
          </p>
          {result && (
            <div className="flex flex-wrap items-center gap-2 mb-3 text-xs text-gray-400">
              <span
                className={`font-semibold rounded-md px-2 py-0.5 ${
                  result.engine === "claude"
                    ? "bg-violet-500/20 text-violet-300"
                    : "bg-amber-500/15 text-amber-300"
                }`}
              >
                {result.engine === "claude" ? "Claude" : "Rule-based demo"}
              </span>
              {result.notice && <span>{result.notice}</span>}
            </div>
          )}
          <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-6 min-h-[200px] mb-6">
            {result ? (
              <article className="prose prose-invert prose-sm max-w-none whitespace-pre-wrap text-gray-200 leading-relaxed">
                {result.memo}
              </article>
            ) : (
              <p className="text-sm text-gray-600">
                {loading ? "Lead orchestrator is planning…" : "Memo will appear here."}
              </p>
            )}
          </div>

          {result && (
            <>
              <p className="text-xs font-semibold tracking-widest text-gray-500 uppercase mb-3">
                {result.engine === "demo" ? "Rule-based steps" : "Sub-agent trace"}
              </p>
              <div className="space-y-3 mb-6">
                {result.trace.map((t, i) => (
                  <TraceEntry key={i} entry={t} />
                ))}
              </div>

              <p className="text-xs font-semibold tracking-widest text-gray-500 uppercase mb-3">
                Usage, all calls
              </p>
              {result.engine === "demo" ? (
                <p className="text-xs text-gray-500">No model calls, so no tokens were used.</p>
              ) : (
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <Stat label="Lead calls" value={result.usage.lead_calls ?? 0} />
                  <Stat label="Sub-agent calls" value={result.usage.subagent_calls ?? 0} />
                  <Stat label="Input tokens" value={result.usage.input_tokens ?? 0} />
                  <Stat label="Output tokens" value={result.usage.output_tokens ?? 0} />
                  <Stat
                    label="Cache write"
                    value={result.usage.cache_creation_input_tokens ?? 0}
                  />
                  <Stat
                    label="Cache read"
                    value={result.usage.cache_read_input_tokens ?? 0}
                    highlight
                  />
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </main>
  );
}

function TraceEntry({ entry }: { entry: Trace }) {
  if (entry.kind === "thinking") {
    return (
      <div className="border border-violet-500/20 bg-violet-500/[0.04] rounded-xl px-4 py-3">
        <div className="flex items-center gap-2 text-xs font-semibold text-violet-300 mb-2">
          <Brain className="w-3.5 h-3.5" /> Lead thinking
        </div>
        <p className="text-xs text-gray-400 leading-relaxed whitespace-pre-wrap">{entry.text}</p>
      </div>
    );
  }
  if (entry.kind === "tool_call") {
    return (
      <div className="border border-cyan-500/20 bg-cyan-500/[0.04] rounded-xl px-4 py-3">
        <div className="flex items-center gap-2 text-xs font-semibold text-cyan-300 mb-1.5">
          <Wrench className="w-3.5 h-3.5" /> {entry.name}
        </div>
        <pre className="text-xs text-gray-400 font-mono overflow-x-auto">
          {JSON.stringify(entry.input, null, 2)}
        </pre>
      </div>
    );
  }
  if (entry.kind === "tool_result") {
    return (
      <div className="border border-emerald-500/15 bg-emerald-500/[0.03] rounded-xl px-4 py-3">
        <div className="flex items-center gap-2 text-xs font-semibold text-emerald-300 mb-1.5">
          <FileText className="w-3.5 h-3.5" /> {entry.name} → response
        </div>
        <p className="text-xs text-gray-400 leading-relaxed whitespace-pre-wrap">{entry.text}</p>
      </div>
    );
  }
  return (
    <div className="border border-rose-500/30 bg-rose-500/[0.04] rounded-xl px-4 py-3">
      <div className="text-xs font-semibold text-rose-300 mb-1">{entry.name}: error</div>
      <p className="text-xs text-gray-400">{entry.text}</p>
    </div>
  );
}

function Stat({
  label,
  value,
  highlight,
}: {
  label: string;
  value: number;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border px-3 py-2 ${
        highlight
          ? "border-violet-500/30 bg-violet-500/[0.05]"
          : "border-white/[0.06] bg-white/[0.02]"
      }`}
    >
      <p className="text-[10px] uppercase tracking-widest text-gray-500">{label}</p>
      <p
        className={`text-base font-bold ${highlight ? "text-violet-300" : "text-white"}`}
      >
        {value.toLocaleString()}
      </p>
    </div>
  );
}
