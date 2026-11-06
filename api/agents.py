"""
Lead orchestrator + three specialist sub-agents.

The lead plans the analysis and dispatches to sub-agents through tool use, and never touches raw data.
Each sub-agent owns one slice of expertise, loads its slice of mock data, and calls a smaller model with
a focused system prompt. Tool calls from one turn run concurrently, and everything a request spends is
counted in `Run` so the UI can show the true totals.
"""

from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from anthropic import Anthropic

from metrics import portfolio_metrics
from mocks import SUPPORTED_TICKERS, get_market_data, get_news

LEAD_MODEL = os.environ.get("LEAD_MODEL", "claude-sonnet-4-6")
SUBAGENT_MODEL = os.environ.get("SUBAGENT_MODEL", "claude-haiku-4-5")

# The Vercel function is killed at 60 seconds (vercel.json). Stopping earlier leaves time to answer.
REQUEST_DEADLINE_S = 50.0
MAX_LEAD_TURNS = 8
MAX_PARALLEL_TOOLS = 8

USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)

_client: Anthropic | None = None


def client() -> Anthropic:
    global _client
    if _client is None:
        # No SDK retries: a retry could outlast the request deadline, and the caller has a fallback.
        _client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], max_retries=0)
    return _client


class AgentStopped(Exception):
    """The lead couldn't produce a memo: refusal, truncation, turn cap, or out of time."""


class Run:
    """State for one request: the time left and the tokens spent across every model call."""

    def __init__(self, deadline_s: float = REQUEST_DEADLINE_S):
        self._deadline = time.monotonic() + deadline_s
        self._lock = threading.Lock()
        self._totals = {field: 0 for field in USAGE_FIELDS}
        self._calls = {"lead": 0, "subagent": 0}

    def create(self, role: str, **params: Any) -> Any:
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise AgentStopped("request deadline reached")
        response = client().with_options(timeout=remaining).messages.create(**params)
        with self._lock:
            self._calls[role] += 1
            for field in USAGE_FIELDS:
                self._totals[field] += getattr(response.usage, field, 0) or 0
        return response

    def usage(self) -> dict[str, int]:
        with self._lock:
            return {
                **self._totals,
                "lead_calls": self._calls["lead"],
                "subagent_calls": self._calls["subagent"],
            }


def _ask_subagent(run: Run, system: str, user_msg: str, max_tokens: int) -> str:
    response = run.create(
        "subagent",
        model=SUBAGENT_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = _first_text(response)
    if response.stop_reason == "refusal" or not text:
        raise RuntimeError(f"no briefing returned (stop_reason={response.stop_reason})")
    return text


# ---------- Sub-agent: market data ----------

MARKET_DATA_SYSTEM = """You are a sell-side equity analyst's market data specialist.

You receive structured market data for a set of tickers and write a tight 3-5 sentence factual brief covering:
- Current price level relative to the 52-week range
- YTD performance and recent daily move
- Valuation snapshot (P/E vs. sector context where you can infer it)
- One sentence on volatility / beta if material

Stay factual. No buy/sell recommendations, no forward predictions. The lead analyst will synthesize. Always cite specific numbers from the data you were given."""


def market_data_subagent(run: Run, tickers: list[str]) -> str:
    data = get_market_data(tickers)
    user_msg = (
        f"Brief the lead analyst on market data for: {', '.join(tickers)}\n\n"
        f"```json\n{json.dumps(data, indent=2)}\n```"
    )
    return _ask_subagent(run, MARKET_DATA_SYSTEM, user_msg, 600)


# ---------- Sub-agent: news sentiment ----------

NEWS_SENTIMENT_SYSTEM = """You are a sell-side equity analyst's news desk.

You receive recent headlines for a set of tickers. For each ticker, output:
- Net sentiment: BULLISH / BEARISH / MIXED / NEUTRAL
- 2-3 bullet drivers (the headlines doing the work)
- One sentence on the asymmetry of risk (where the surprises could come from)

Be concise. No price targets. The lead analyst will weigh this against fundamentals."""


def news_sentiment_subagent(run: Run, tickers: list[str], window: str = "recent") -> str:
    news = get_news(tickers)
    user_msg = (
        f"Brief the lead analyst on {window} news sentiment for: {', '.join(tickers)}\n\n"
        f"```json\n{json.dumps(news, indent=2)}\n```"
    )
    return _ask_subagent(run, NEWS_SENTIMENT_SYSTEM, user_msg, 900)


# ---------- Sub-agent: risk concentration ----------

RISK_SYSTEM = """You are a sell-side risk specialist.

You receive a portfolio (ticker → weight), metrics already computed from it, and market data including betas and volatility. Output:
- Top 2 single-name concentrations with weights
- Sector concentration (rolled-up sector weights)
- Portfolio beta
- One sentence flagging the dominant tail risk implied by the concentration

Report the computed metrics exactly as given. Don't recalculate them. Be quantitative. No recommendations. The lead analyst will translate."""


def risk_concentration_subagent(run: Run, holdings: dict[str, float]) -> str:
    tickers = list(holdings.keys())
    data = get_market_data(tickers)
    payload = {
        "holdings": holdings,
        "computed_metrics": portfolio_metrics(holdings),
        "market_data": {
            t: {
                "sector": data[t].get("sector"),
                "beta_3y": data[t].get("beta_3y"),
                "daily_volatility_30d": data[t].get("daily_volatility_30d"),
            }
            for t in tickers
            if "error" not in data[t]
        },
    }
    user_msg = (
        "Analyze concentration and risk for this portfolio.\n\n"
        f"```json\n{json.dumps(payload, indent=2)}\n```"
    )
    return _ask_subagent(run, RISK_SYSTEM, user_msg, 700)


# ---------- Lead orchestrator ----------

LEAD_SYSTEM = f"""You are a senior portfolio analyst at a sell-side investment bank.

You answer client questions about portfolios by dispatching to three specialist sub-agents and synthesizing their briefings into a sharp, decision-grade memo.

Sub-agents available:
- query_market_data(tickers): price action, valuation, vol
- query_news_sentiment(tickers, window): recent headlines, sentiment, drivers
- analyze_risk_concentration(holdings): concentration and risk metrics

Workflow:
1. Read the client question and portfolio carefully.
2. Decide which sub-agents to invoke and with what arguments. You may call them in parallel.
3. Synthesize the briefings into a short analyst memo that directly answers the client question: 3 paragraphs, under 250 words in total. Lead with the answer; support it with the sub-agent findings that matter most; close with the one risk that, if it materializes, breaks the thesis.

Style:
- Start with the answer itself: no title, header, date, byline, or sign-off.
- Keep it short because the client reads it on screen while waiting; choose the strongest evidence rather than all of it.
- Specific over vague: cite numbers from sub-agent briefings.
- Attribute findings explicitly ("the news desk flags...", "risk specialist notes...").
- No hedging language ("might", "could potentially", "it depends"). Pick a side.
- Currently in coverage: {', '.join(SUPPORTED_TICKERS)}. If asked about anything else, say so and proceed with the rest."""


TOOLS = [
    {
        "name": "query_market_data",
        "description": "Get a market data brief from the market data sub-agent — price, valuation, volatility for the given tickers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of ticker symbols",
                }
            },
            "required": ["tickers"],
        },
    },
    {
        "name": "query_news_sentiment",
        "description": "Get a news sentiment brief from the news desk sub-agent — recent headlines, net sentiment, key drivers for the given tickers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of ticker symbols",
                },
                "window": {
                    "type": "string",
                    "description": "News time window descriptor (e.g. 'last week', 'recent')",
                },
            },
            "required": ["tickers"],
        },
    },
    {
        "name": "analyze_risk_concentration",
        "description": "Get a risk and concentration analysis from the risk specialist sub-agent for a portfolio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "holdings": {
                    "type": "object",
                    "description": "Mapping of ticker to weight (weights should sum to ~1.0)",
                    "additionalProperties": {"type": "number"},
                }
            },
            "required": ["holdings"],
        },
    },
]


SUBAGENT_DISPATCH = {
    "query_market_data": lambda run, inp: market_data_subagent(run, inp["tickers"]),
    "query_news_sentiment": lambda run, inp: news_sentiment_subagent(
        run, inp["tickers"], inp.get("window", "recent")
    ),
    "analyze_risk_concentration": lambda run, inp: risk_concentration_subagent(run, inp["holdings"]),
}


def _run_tool(run: Run, block: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run one sub-agent. A failure goes back to the lead as an error it can work around."""
    trace: list[dict[str, Any]] = [{"kind": "tool_call", "name": block.name, "input": block.input}]
    try:
        if block.name not in SUBAGENT_DISPATCH:
            raise ValueError("unknown tool")
        text = SUBAGENT_DISPATCH[block.name](run, block.input)
    except Exception as e:
        err = f"Sub-agent {block.name} failed: {e}"
        trace.append({"kind": "tool_error", "name": block.name, "text": err})
        return trace, {"type": "tool_result", "tool_use_id": block.id, "content": err, "is_error": True}
    trace.append({"kind": "tool_result", "name": block.name, "text": text})
    return trace, {"type": "tool_result", "tool_use_id": block.id, "content": text}


def run_lead(query: str, holdings: dict[str, float], deadline_s: float = REQUEST_DEADLINE_S) -> dict[str, Any]:
    """Run the lead through a full tool-use loop and return the memo, trace, and total usage.

    Raises AgentStopped, or an anthropic.APIError, if there's no memo to return.
    """
    run = Run(deadline_s)
    trace: list[dict[str, Any]] = []
    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": (
                f"Client question: {query}\n\n"
                f"Portfolio (ticker → weight):\n"
                f"```json\n{json.dumps(holdings, indent=2)}\n```"
            ),
        }
    ]

    for _ in range(MAX_LEAD_TURNS):
        resp = run.create(
            "lead",
            model=LEAD_MODEL,
            max_tokens=8000,
            thinking={"type": "adaptive"},
            # Marks the newest block, so the prefix grows with each tool turn. Below the model's
            # minimum prefix size this silently does nothing, which `usage` will show.
            cache_control={"type": "ephemeral"},
            system=LEAD_SYSTEM,
            tools=TOOLS,
            messages=messages,
        )

        for block in resp.content:
            if block.type == "thinking" and getattr(block, "thinking", ""):
                trace.append({"kind": "thinking", "text": block.thinking})

        if resp.stop_reason == "end_turn":
            return {"memo": _first_text(resp), "trace": trace, "usage": run.usage()}
        if resp.stop_reason != "tool_use":
            raise AgentStopped(f"lead stopped with stop_reason={resp.stop_reason}")

        calls = [block for block in resp.content if block.type == "tool_use"]
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_TOOLS) as pool:
            finished = list(pool.map(lambda block: _run_tool(run, block), calls))

        # All results go back in one user message, in call order. The full assistant content goes
        # back too, because thinking blocks have to stay with the turn that produced them.
        for tool_trace, _ in finished:
            trace.extend(tool_trace)
        messages.append({"role": "assistant", "content": resp.content})
        messages.append({"role": "user", "content": [result for _, result in finished]})

    raise AgentStopped(f"no memo after {MAX_LEAD_TURNS} turns")


def _first_text(resp: Any) -> str:
    return "".join(b.text for b in resp.content if b.type == "text").strip()
