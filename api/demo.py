"""The no-model engine: real calculations over the mock data, written up from a fixed template.

It runs when Claude can't, so the demo keeps working. It doesn't read the client's question, and the
memo says so rather than passing a template off as analysis.
"""

from __future__ import annotations

from typing import Any

from metrics import portfolio_metrics
from mocks import MARKET_DATA, NEWS


def _market_brief(tickers: list[str]) -> str:
    lines = []
    for ticker in tickers:
        d = MARKET_DATA[ticker]
        lines.append(
            f"{ticker} ({d['name']}): ${d['price']:.2f}, {d['ytd_change_pct']:+.1f}% YTD, "
            f"52-week range ${d['52w_low']:.2f} to ${d['52w_high']:.2f}, P/E {d['pe_ttm']:.1f}, "
            f"beta {d['beta_3y']:.2f}."
        )
    return "\n".join(lines)


def _news_brief(tickers: list[str]) -> str:
    lines = []
    for ticker in tickers:
        for item in NEWS.get(ticker, [])[:2]:
            lines.append(f"{ticker}: {item['headline']}")
    return "\n".join(lines) or "No headlines in coverage."


def _risk_brief(metrics: dict[str, Any]) -> str:
    top = ", ".join(f"{p['ticker']} {p['weight']:.0%}" for p in metrics["top_positions"])
    sectors = ", ".join(f"{s} {w:.0%}" for s, w in metrics["sector_weights"].items())
    return f"Largest positions: {top}.\nSector weights: {sectors}.\nPortfolio beta: {metrics['portfolio_beta']:.2f}."


def run_demo(holdings: dict[str, float]) -> dict[str, Any]:
    """Build a memo and trace in the same shape the Claude engine returns."""
    metrics = portfolio_metrics(holdings)
    tickers = [p for p in sorted(holdings, key=lambda t: (-holdings[t], t)) if p in MARKET_DATA]
    uncovered = metrics["uncovered_tickers"]
    if not tickers:
        return {
            "memo": f"None of these tickers are in coverage: {', '.join(uncovered)}. "
            f"Coverage is {', '.join(MARKET_DATA)}.",
            "trace": [],
            "usage": {},
        }

    market, news, risk = _market_brief(tickers), _news_brief(tickers), _risk_brief(metrics)
    trace = [
        {"kind": "tool_call", "name": "query_market_data", "input": {"tickers": tickers}},
        {"kind": "tool_result", "name": "query_market_data", "text": market},
        {"kind": "tool_call", "name": "query_news_sentiment", "input": {"tickers": tickers}},
        {"kind": "tool_result", "name": "query_news_sentiment", "text": news},
        {"kind": "tool_call", "name": "analyze_risk_concentration", "input": {"holdings": holdings}},
        {"kind": "tool_result", "name": "analyze_risk_concentration", "text": risk},
    ]

    positions = " and ".join(f"{p['ticker']} at {p['weight']:.0%}" for p in metrics["top_positions"])
    sector, sector_weight = next(iter(metrics["sector_weights"].items()))
    driver = metrics["largest_beta_contributor"]
    driver_data = MARKET_DATA[driver]
    memo = [
        "This is a rule-based summary. No model read your question, so it describes the portfolio "
        "rather than answering you directly.",
        f"The largest positions are {positions}, and {sector} is the largest sector at "
        f"{sector_weight:.0%}. Portfolio beta is {metrics['portfolio_beta']:.2f}.",
        f"{driver} contributes the most to that beta. It is {driver_data['ytd_change_pct']:+.1f}% year "
        f"to date with a beta of {driver_data['beta_3y']:.2f} and a P/E of {driver_data['pe_ttm']:.1f}.",
    ]
    if uncovered:
        memo.append(f"Not in coverage, so left out of these figures: {', '.join(uncovered)}.")
    return {"memo": "\n\n".join(memo), "trace": trace, "usage": {}}
