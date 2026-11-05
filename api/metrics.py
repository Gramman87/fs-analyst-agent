"""Portfolio arithmetic, done in code so the numbers in a memo never depend on a model's math."""

from __future__ import annotations

from typing import Any

from mocks import MARKET_DATA


def portfolio_metrics(holdings: dict[str, float]) -> dict[str, Any]:
    """Concentration and beta for a portfolio. Tickers outside coverage are reported, not guessed.

    Beta and sector weights are computed over the covered weight only, and `covered_weight` says how
    much of the portfolio that is.
    """
    covered = {t.upper(): w for t, w in holdings.items() if t.upper() in MARKET_DATA}
    uncovered = sorted(t.upper() for t in holdings if t.upper() not in MARKET_DATA)
    covered_weight = sum(covered.values())

    sectors: dict[str, float] = {}
    beta_contributions: dict[str, float] = {}
    for ticker, weight in covered.items():
        sector = MARKET_DATA[ticker]["sector"]
        sectors[sector] = sectors.get(sector, 0.0) + weight
        beta_contributions[ticker] = weight * MARKET_DATA[ticker]["beta_3y"]

    top = sorted(covered.items(), key=lambda item: (-item[1], item[0]))[:2]
    biggest_beta = max(beta_contributions, key=lambda t: (beta_contributions[t], t), default=None)
    return {
        "top_positions": [{"ticker": t, "weight": round(w, 4)} for t, w in top],
        "sector_weights": {
            s: round(w, 4) for s, w in sorted(sectors.items(), key=lambda item: (-item[1], item[0]))
        },
        "portfolio_beta": round(sum(beta_contributions.values()) / covered_weight, 2) if covered_weight > 0 else None,
        "largest_beta_contributor": biggest_beta,
        "covered_weight": round(covered_weight, 4),
        "uncovered_tickers": uncovered,
    }
