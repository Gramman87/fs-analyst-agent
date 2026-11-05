# Portfolio Analyst Agent

**Live demo:** https://fs-analyst-agent.vercel.app

A financial-services portfolio analyst built as a lead orchestrator with three specialist sub-agents on the Claude API. The lead plans the analysis and dispatches through tool use, the sub-agents each own one slice of the work, and the result is a memo an analyst could hand to a portfolio manager. All market data and news are fictional.

## How it works

```
  client question + portfolio
            │
            ▼
   ┌────────────────────────────┐
   │  LEAD ORCHESTRATOR         │  claude-sonnet-4-6
   │  plans, then writes memo   │  adaptive thinking
   └──────────────┬─────────────┘
                  │ tool use, run concurrently
        ┌─────────┼─────────┐
        ▼         ▼         ▼
   ┌────────┐ ┌────────┐ ┌────────┐
   │ MARKET │ │ NEWS   │ │ RISK   │  claude-haiku-4-5
   │ DATA   │ │ DESK   │ │        │
   └────────┘ └────────┘ └────────┘
                  │
                  ▼
        memo + trace + usage
```

- **The lead never touches raw data.** It only sees sub-agent briefings.
- **Sub-agents in the same turn run concurrently,** and their results go back in one message in call order.
- **Calculations are done in code.** Portfolio beta and sector weights come from `api/metrics.py`, and the risk sub-agent is told to report them rather than redo the math.
- **A failed sub-agent doesn't end the request.** The lead gets the error and works with what it has.

## Which engine answers

Every response says which engine wrote it, so a template is never presented as model output.

| Situation | Who answers |
| --------- | ----------- |
| API key set, under the daily limit | Claude |
| No API key | Rule-based demo |
| Daily limit reached | Rule-based demo, with no API call |
| API error, refusal, truncated memo, or past the 50-second deadline | Rule-based demo |

The demo engine does real calculations over the mock data, but it doesn't read the question, and its memo says so.

`ANALYZE_DAILY_LIMIT` is counted per server instance and resets on a cold start, so it limits runaway use without being a hard cap. Set a spending limit on the API key for that.

## Prompt caching

Requests set a cache marker, and the UI reports cache writes and reads across every model call in the request. Expect low numbers with the default models:

- A prefix only caches above a model-specific minimum, and shorter prefixes silently don't. That minimum is 1,024 tokens for Sonnet 4.6 and 4,096 for Haiku 4.5.
- The lead's tools and system prompt come to roughly 600 tokens, so its first turn can't cache. The prefix can only pass the minimum once briefings are in the conversation.
- The sub-agent prompts are around 100 tokens and will never reach the Haiku 4.5 minimum, so they don't set a marker.

## Evals

`evals/run_eval.py` runs five hand-written cases against the live API and scores each one:

| Check | What it does | Fails the case? |
| ----- | ------------ | --------------- |
| Routing | The lead called the expected sub-agents | Yes |
| Coverage | The memo mentions required terms, as whole words | Yes |
| Judge | A separate model scores accuracy, specificity, and decisiveness from 1 to 5 | Yes, below 3 or if the reply is unreadable |
| Grounding | Lists figures in the memo that appear in no briefing | No, it's for review, because a memo can derive a number |

```bash
source .venv/bin/activate
ANTHROPIC_API_KEY=... python evals/run_eval.py
```

This spends API credits, so it runs by hand and isn't part of CI. Results are saved to `evals/last_run.json`. Five cases can catch regressions, but they aren't a quality measurement.

## Run it locally

```bash
npm install
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt

npm run dev:api    # the Python API on :8000
npm run dev        # the UI on http://localhost:3000, in a second terminal
```

Without a key, it runs on the demo engine. To use Claude, export the variables in `.env.example` before `npm run dev:api`.

## Test

```bash
.venv/bin/python -m pytest
npm run lint && npm run typecheck && npm run build
```

The tests need no API key and remove any key in your environment, so they never spend credits. They run the real Anthropic SDK against a local transport, which covers request building, response parsing, the tool loop, each fallback path, and the eval's scoring. That shows the app handles the API as modeled in the tests. It doesn't replace a run against the live API.

## Deploy

Import the repo into Vercel and set `ANTHROPIC_API_KEY`. Next.js serves the UI and `api/analyze.py` deploys as a Python function, with a 60-second limit set in `vercel.json`.

## Limitations

- **Mock data:** five tickers with hand-written figures and headlines.
- **Stateless:** nothing is saved between requests.
- **No authentication:** anyone can call the endpoint, so it relies on input limits, the daily limit, and the key's spending limit.

## Files

```
api/
  analyze.py    HTTP handler and input validation
  engine.py     Chooses the engine, daily limit
  agents.py     Lead orchestrator and sub-agents
  demo.py       Rule-based engine
  metrics.py    Portfolio calculations
  mocks.py      Mock market data and news
app/            Next.js UI
evals/          Cases, scoring rules, and the live runner
tests/          Offline tests
scripts/        Local API server
```
