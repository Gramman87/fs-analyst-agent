# Portfolio Analyst Agent — Claude Sub-Agent POC

A financial-services portfolio analyst built as a **lead orchestrator + three specialist sub-agents** on the Claude API. The lead (Sonnet 4.6, adaptive thinking) plans the analysis and dispatches to sub-agents (Haiku 4.5) via tool-use; the sub-agents own a slice of domain expertise each. The final memo is what an analyst would hand to a portfolio manager.

Built as a demo for the kind of production deployment patterns an Anthropic Forward Deployed Engineer ships to enterprise customers.

## Live demo

UI: enter a portfolio + a client question, get a memo back. The right panel surfaces the lead's thinking, every sub-agent invocation, and the cache hit/miss telemetry.

## Architecture

```
  client question + portfolio
            │
            ▼
   ┌────────────────────────────┐
   │  LEAD ORCHESTRATOR         │  Sonnet 4.6
   │  (adaptive thinking)       │  + cached system prompt + cached tool defs
   │                            │
   │  Tools (= sub-agents):     │
   │   • query_market_data      │
   │   • query_news_sentiment   │
   │   • analyze_risk_…         │
   └──────────────┬─────────────┘
                  │ tool_use loop
        ┌─────────┼─────────┐
        ▼         ▼         ▼
  ┌──────────┐ ┌──────────┐ ┌──────────┐
  │ MARKET   │ │ NEWS     │ │ RISK     │  Haiku 4.5
  │ DATA     │ │ SENTIMENT│ │ CONCENT. │  + cached system prompts
  └──────────┘ └──────────┘ └──────────┘
        │         │         │
        └─────────┼─────────┘
                  ▼
       analyst memo + trace
```

The lead never touches raw data — it only sees sub-agent briefings. Each sub-agent loads its own data slice (mocked here; replace with a real provider in production) and calls Haiku with a focused system prompt.

## What this demonstrates

| FDE Applied AI JD beat | Where it lives in this repo |
|---|---|
| Production application on Claude | `api/analyze.py` — Vercel serverless function |
| Sub-agents | `api/agents.py` — three Haiku-backed sub-agents invoked via tool-use |
| Agent skills | Each sub-agent's system prompt is its skill — focused, cached, replaceable |
| Evaluation frameworks | `evals/run_eval.py` — 5 hand-written cases, routing + coverage checks, Claude-as-judge with Opus 4.7 |
| Repeatable deployment pattern | Lead/sub-agent split + cache placement + eval harness is portable to any vertical |
| Python proficiency | All backend logic in Python; Next.js TS only for the frontend |
| Enterprise verticals | Flavored for financial services (portfolio analysis); the pattern is vertical-neutral |

## Prompt caching strategy

Caching is a prefix match — any byte change in the prefix invalidates everything after. Render order is `tools → system → messages`, so:

- **Lead**: `cache_control: ephemeral` on the system prompt block. Since `tools` render before `system`, this caches **both tool defs + system** in one breakpoint. The tool-use loop makes 2-N `messages.create` calls per request; iterations 2+ all hit cache for the tools+system prefix.
- **Sub-agents**: `cache_control: ephemeral` on each sub-agent's system prompt. If the lead invokes the same sub-agent twice in one analysis (e.g. market data on multiple ticker sets), the second call reads from cache.

Telemetry: the UI surfaces `cache_creation_input_tokens` (write, ~1.25×) vs `cache_read_input_tokens` (read, ~0.1×). Cache reads should dominate after the first iteration.

## Model choice

| Role | Model | Why |
|---|---|---|
| Lead orchestrator | `claude-sonnet-4-6` | Strong tool-use planning at lower cost than Opus; adaptive thinking included |
| Sub-agents | `claude-haiku-4-5` | Cheap, fast, focused tasks; the sub-agent system prompts do the heavy lifting |
| Eval judge | `claude-opus-4-7` (effort: high) | Most capable model for grading; runs offline, cost not in critical path |

This mirrors Anthropic's own canonical pattern (Claude Code uses Haiku for its Explore sub-agents).

## Running locally

```bash
cp .env.example .env.local       # add your ANTHROPIC_API_KEY
npm install
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
npm run dev                       # http://localhost:3000
```

The Python serverless function under `api/analyze.py` is served by Vercel's Python runtime (or `vercel dev` locally). Next.js handles the frontend.

## Running the evals

```bash
source .venv/bin/activate
ANTHROPIC_API_KEY=sk-ant-... python evals/run_eval.py
```

Output:
- per-case pass/fail on routing + coverage
- per-case judge scores on accuracy / specificity / decisiveness (1-5 each)
- aggregate pass rates and judge averages
- full results dumped to `evals/last_run.json`
- non-zero exit if any case fails — wire into CI

## Deployment to Vercel

1. Push to a GitHub repo
2. Import to Vercel — it detects Next.js automatically
3. Set `ANTHROPIC_API_KEY` in the Vercel project's env vars
4. The Python serverless function under `api/` deploys alongside the Next.js app

`vercel.json` sets `maxDuration: 60` for the Python function (the lead's tool-use loop can take 15-30s on a full 3-sub-agent dispatch).

## Limitations

- **Mock data.** `api/mocks.py` ships hand-written market data and news for 5 tickers. Production would swap in a real provider (Polygon, FMP, Benzinga, etc.).
- **Coverage is small.** 5 tickers. Adding more is just adding entries to `mocks.py`.
- **No portfolio persistence.** Each request is stateless.
- **Eval cases are hand-written.** Five cases is enough to catch regressions but you'd want 20-50 for production confidence.

## Files

```
fs-analyst-agent/
├── api/
│   ├── analyze.py       # Vercel serverless entry point
│   ├── agents.py        # Lead orchestrator + 3 sub-agents
│   └── mocks.py         # Mock market data + news corpus
├── app/                 # Next.js frontend (TS)
├── evals/
│   ├── cases.py         # Hand-written test cases
│   └── run_eval.py      # Runner with Claude-as-judge scoring
└── vercel.json          # Python function config (60s max duration)
```
