"""
Lead orchestrator + three specialist sub-agents.

Architecture:
- Lead (Sonnet 4.6, adaptive thinking) plans the analysis and dispatches
  to sub-agents via tool-use. The lead never touches raw data.
- Sub-agents (Haiku 4.5) each own one slice of domain expertise:
    * market_data_subagent  — price action, valuation, vol
    * news_sentiment_subagent — headlines, drivers, tone
    * risk_concentration_subagent — sector / single-name concentration
  Each sub-agent loads its slice of mock data and calls Haiku with a
  focused, cached system prompt.
- Caching: every system prompt + the lead's tool definitions are marked
  cacheable. On the lead's tool-use loop, subsequent iterations hit cache
  for tools+system; sub-agent calls within the same request hit cache for
  their system prompts after the first call.
"""

from __future__ import annotations

import json
import os
from typing import Any

from anthropic import Anthropic

from mocks import SUPPORTED_TICKERS, get_market_data, get_news

LEAD_MODEL = "claude-sonnet-4-6"
SUBAGENT_MODEL = "claude-haiku-4-5"

_client: Anthropic | None = None


def client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


# ---------- Sub-agent: market data ----------

MARKET_DATA_SYSTEM = """You are a sell-side equity analyst's market data specialist.

You receive structured market data for a set of tickers and write a tight 3-5 sentence factual brief covering:
- Current price level relative to the 52-week range
- YTD performance and recent daily move
- Valuation snapshot (P/E vs. sector context where you can infer it)
- One sentence on volatility / beta if material

Stay factual. No buy/sell recommendations, no forward predictions. The lead analyst will synthesize. Always cite specific numbers from the data you were given."""


def market_data_subagent(tickers: list[str]) -> str:
    data = get_market_data(tickers)
    user_msg = (
        f"Brief the lead analyst on market data for: {', '.join(tickers)}\n\n"
        f"```json\n{json.dumps(data, indent=2)}\n```"
    )
    resp = client().messages.create(
        model=SUBAGENT_MODEL,
        max_tokens=600,
        system=[
            {
                "type": "text",
                "text": MARKET_DATA_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_msg}],
    )
    return _first_text(resp)


# ---------- Sub-agent: news sentiment ----------

NEWS_SENTIMENT_SYSTEM = """You are a sell-side equity analyst's news desk.

You receive recent headlines for a set of tickers. For each ticker, output:
- Net sentiment: BULLISH / BEARISH / MIXED / NEUTRAL
- 2-3 bullet drivers (the headlines doing the work)
- One sentence on the asymmetry of risk (where the surprises could come from)

Be concise. No price targets. The lead analyst will weigh this against fundamentals."""


def news_sentiment_subagent(tickers: list[str], window: str = "recent") -> str:
    news = get_news(tickers)
    user_msg = (
        f"Brief the lead analyst on {window} news sentiment for: {', '.join(tickers)}\n\n"
        f"```json\n{json.dumps(news, indent=2)}\n```"
    )
    resp = client().messages.create(
        model=SUBAGENT_MODEL,
        max_tokens=900,
        system=[
            {
                "type": "text",
                "text": NEWS_SENTIMENT_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_msg}],
    )
    return _first_text(resp)


# ---------- Sub-agent: risk concentration ----------

RISK_SYSTEM = """You are a sell-side risk specialist.

You receive a portfolio (ticker → weight) and structured market data including sectors and betas. Output:
- Top 2 single-name concentrations with weights
- Sector concentration (rolled-up sector weights)
- Portfolio beta estimate (weighted average of name betas)
- One sentence flagging the dominant tail risk implied by the concentration

Be quantitative. No recommendations. The lead analyst will translate."""


def risk_concentration_subagent(holdings: dict[str, float]) -> str:
    tickers = list(holdings.keys())
    data = get_market_data(tickers)
    payload = {
        "holdings": holdings,
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
    resp = client().messages.create(
        model=SUBAGENT_MODEL,
        max_tokens=700,
        system=[
            {
                "type": "text",
                "text": RISK_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_msg}],
    )
    return _first_text(resp)


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
3. Synthesize the briefings into a 4-6 paragraph analyst memo that directly answers the client question. Lead with the answer; support with sub-agent findings; close with the one risk that, if it materializes, breaks the thesis.

Style:
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
    "query_market_data": lambda inp: market_data_subagent(inp["tickers"]),
    "query_news_sentiment": lambda inp: news_sentiment_subagent(
        inp["tickers"], inp.get("window", "recent")
    ),
    "analyze_risk_concentration": lambda inp: risk_concentration_subagent(inp["holdings"]),
}


def run_lead(query: str, holdings: dict[str, float]) -> dict[str, Any]:
    """Run the lead orchestrator through a full tool-use loop. Returns memo + trace."""
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

    for _ in range(8):  # hard cap on iterations
        resp = client().messages.create(
            model=LEAD_MODEL,
            max_tokens=4000,
            thinking={"type": "adaptive"},
            system=[
                {
                    "type": "text",
                    "text": LEAD_SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=TOOLS,
            messages=messages,
        )

        # Record any thinking the lead did this turn
        for block in resp.content:
            if block.type == "thinking" and getattr(block, "thinking", ""):
                trace.append({"kind": "thinking", "text": block.thinking})

        if resp.stop_reason == "end_turn":
            memo = "".join(b.text for b in resp.content if b.type == "text")
            usage = resp.usage
            return {
                "memo": memo,
                "trace": trace,
                "usage": {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0),
                    "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0),
                },
            }

        if resp.stop_reason != "tool_use":
            return {
                "memo": f"_Lead halted with stop_reason={resp.stop_reason}._",
                "trace": trace,
                "usage": {},
            }

        # Execute every tool_use block this turn, in order
        tool_results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            tool_name = block.name
            tool_input = block.input
            trace.append({"kind": "tool_call", "name": tool_name, "input": tool_input})
            try:
                result_text = SUBAGENT_DISPATCH[tool_name](tool_input)
                trace.append({"kind": "tool_result", "name": tool_name, "text": result_text})
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text,
                    }
                )
            except Exception as e:  # surface the error to the lead, don't crash
                err = f"Sub-agent {tool_name} failed: {e}"
                trace.append({"kind": "tool_error", "name": tool_name, "text": err})
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": err,
                        "is_error": True,
                    }
                )

        # Append full assistant content (preserves thinking blocks) + tool results
        messages.append({"role": "assistant", "content": resp.content})
        messages.append({"role": "user", "content": tool_results})

    return {
        "memo": "_Iteration cap reached without end_turn — likely a prompt or tooling issue._",
        "trace": trace,
        "usage": {},
    }


def _first_text(resp: Any) -> str:
    return "".join(b.text for b in resp.content if b.type == "text").strip()
