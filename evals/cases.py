"""Hand-written eval cases. Each names the query, portfolio, expected sub-agents,
and terms the memo must mention as whole words. "a|b" accepts either spelling."""

CASES = [
    {
        "id": "tech_heavy_fed_risk",
        "query": "I'm overweight tech going into the next Fed meeting. Should I be worried, and what's the biggest single-name risk?",
        "holdings": {"AAPL": 0.3, "MSFT": 0.3, "NVDA": 0.3, "JPM": 0.05, "XOM": 0.05},
        "expected_tools": {
            "query_market_data",
            "query_news_sentiment",
            "analyze_risk_concentration",
        },
        "must_mention": ["NVDA", "tech|technology", "concentration|concentrated"],
    },
    {
        "id": "rate_cut_value_thesis",
        "query": "I built this for a rate-cut cycle with a value tilt. Does the current setup support that thesis or am I wrong?",
        "holdings": {"JPM": 0.5, "XOM": 0.3, "AAPL": 0.1, "MSFT": 0.1},
        "expected_tools": {
            "query_market_data",
            "query_news_sentiment",
            "analyze_risk_concentration",
        },
        "must_mention": ["JPM", "rate"],
    },
    {
        "id": "asymmetry_balanced",
        "query": "What's most likely to surprise me on the upside vs. the downside in this portfolio?",
        "holdings": {"MSFT": 0.25, "AAPL": 0.2, "NVDA": 0.15, "JPM": 0.3, "XOM": 0.1},
        "expected_tools": {"query_news_sentiment"},
        "must_mention": ["upside", "downside"],
    },
    {
        "id": "single_name_news_only",
        "query": "Just tell me what's moving NVDA right now and what I should be watching.",
        "holdings": {"NVDA": 1.0},
        "expected_tools": {"query_news_sentiment"},
        "must_mention": ["NVDA", "China"],
    },
    {
        "id": "energy_overweight",
        "query": "I'm heavily exposed to energy. What's the immediate downside scenario I should be planning for?",
        "holdings": {"XOM": 0.7, "JPM": 0.2, "MSFT": 0.1},
        "expected_tools": {"query_news_sentiment", "analyze_risk_concentration"},
        "must_mention": ["XOM", "Brent"],
    },
]
