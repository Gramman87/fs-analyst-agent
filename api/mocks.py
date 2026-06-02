"""Mock market data + news corpus. Replace with real data sources in production."""

MARKET_DATA = {
    "AAPL": {
        "name": "Apple Inc.",
        "sector": "Information Technology",
        "industry": "Consumer Electronics",
        "price": 234.50,
        "daily_change_pct": -0.82,
        "ytd_change_pct": 12.4,
        "52w_high": 260.10,
        "52w_low": 164.08,
        "market_cap_b": 3540.0,
        "pe_ttm": 36.2,
        "beta_3y": 1.21,
        "daily_volatility_30d": 1.42,
    },
    "MSFT": {
        "name": "Microsoft Corporation",
        "sector": "Information Technology",
        "industry": "Software & Cloud",
        "price": 442.10,
        "daily_change_pct": 0.31,
        "ytd_change_pct": 9.8,
        "52w_high": 468.35,
        "52w_low": 376.32,
        "market_cap_b": 3290.0,
        "pe_ttm": 35.8,
        "beta_3y": 0.93,
        "daily_volatility_30d": 1.18,
    },
    "NVDA": {
        "name": "NVIDIA Corporation",
        "sector": "Information Technology",
        "industry": "Semiconductors",
        "price": 156.20,
        "daily_change_pct": -2.45,
        "ytd_change_pct": 38.7,
        "52w_high": 195.80,
        "52w_low": 88.46,
        "market_cap_b": 3830.0,
        "pe_ttm": 64.5,
        "beta_3y": 1.78,
        "daily_volatility_30d": 3.10,
    },
    "JPM": {
        "name": "JPMorgan Chase & Co.",
        "sector": "Financials",
        "industry": "Diversified Banks",
        "price": 268.40,
        "daily_change_pct": 0.94,
        "ytd_change_pct": 18.2,
        "52w_high": 280.55,
        "52w_low": 195.30,
        "market_cap_b": 760.0,
        "pe_ttm": 13.4,
        "beta_3y": 1.06,
        "daily_volatility_30d": 1.05,
    },
    "XOM": {
        "name": "Exxon Mobil Corporation",
        "sector": "Energy",
        "industry": "Integrated Oil & Gas",
        "price": 112.85,
        "daily_change_pct": 1.23,
        "ytd_change_pct": -4.6,
        "52w_high": 126.34,
        "52w_low": 99.92,
        "market_cap_b": 495.0,
        "pe_ttm": 14.1,
        "beta_3y": 0.84,
        "daily_volatility_30d": 1.31,
    },
}


NEWS = {
    "AAPL": [
        {
            "headline": "Apple unveils on-device foundation model for iOS 19",
            "summary": "Apple announced a 30B-parameter on-device foundation model shipping with iOS 19, claiming sub-200ms latency on A18 Pro silicon. Wall Street largely shrugged; analysts question whether it accelerates services revenue.",
            "tone": "neutral",
        },
        {
            "headline": "DOJ antitrust case against Apple advances to discovery phase",
            "summary": "The Department of Justice's antitrust suit alleging Apple maintains an iPhone monopoly through restrictive App Store policies advanced past Apple's motion to dismiss. A trial date is set for Q3 2027.",
            "tone": "bearish",
        },
        {
            "headline": "Vision Pro 2 production reportedly cut 40% on weak demand",
            "summary": "Supply chain sources report Apple has cut Vision Pro 2 production targets by ~40% amid soft consumer demand. The cut is small in absolute revenue terms but raises questions about the spatial computing thesis.",
            "tone": "bearish",
        },
    ],
    "MSFT": [
        {
            "headline": "Azure AI revenue up 84% YoY; capacity-constrained through 2027",
            "summary": "Microsoft's Q3 earnings showed Azure AI services revenue up 84% YoY, but CFO acknowledged 'meaningful capacity constraints' continuing through fiscal 2027 despite $80B in datacenter capex.",
            "tone": "bullish",
        },
        {
            "headline": "Copilot enterprise seat growth decelerates QoQ",
            "summary": "Enterprise Copilot seat growth decelerated from 31% QoQ to 19% QoQ. Bulls call it normalization; bears point to ROI skepticism in CFO surveys.",
            "tone": "mixed",
        },
    ],
    "NVDA": [
        {
            "headline": "China export controls expanded to cover GB300 series",
            "summary": "The U.S. Commerce Department expanded export controls to cover NVIDIA's GB300 series chips, with no compliant variant currently available. China was ~14% of data center revenue last quarter.",
            "tone": "bearish",
        },
        {
            "headline": "Major hyperscaler signs $40B multi-year GPU commitment",
            "summary": "An unnamed hyperscaler signed a $40B multi-year GPU commitment with NVIDIA, the largest single deal disclosed to date. Pricing terms not disclosed.",
            "tone": "bullish",
        },
        {
            "headline": "Custom-silicon competition from MTIA and TPU showing real workload share",
            "summary": "Meta's MTIA v3 and Google's TPU v7 are now serving meaningful inference workload share internally. Goldman estimates 6-9% of total hyperscaler inference is now on custom silicon vs. 2% a year ago.",
            "tone": "bearish",
        },
    ],
    "JPM": [
        {
            "headline": "Jamie Dimon flags 'caution lights flashing' on commercial real estate",
            "summary": "CEO Jamie Dimon, on the Q3 earnings call, said the bank is seeing 'caution lights flashing' in commercial real estate, particularly office. Reserves were built modestly.",
            "tone": "mixed",
        },
        {
            "headline": "Net interest income guide raised; deposit beta stabilizing",
            "summary": "JPM raised its 2026 NII guide to $94-96B (from $92-94B). Deposit beta is stabilizing earlier than peers, supporting NIM through a potential rate-cut cycle.",
            "tone": "bullish",
        },
    ],
    "XOM": [
        {
            "headline": "Permian production guide raised; Pioneer integration ahead of schedule",
            "summary": "Exxon raised Permian production guidance to 1.45M boe/d for 2026 (from 1.40M), citing faster-than-expected Pioneer integration synergies.",
            "tone": "bullish",
        },
        {
            "headline": "OPEC+ extends voluntary cuts; Brent forecast lowered to $68",
            "summary": "OPEC+ extended voluntary supply cuts through Q2 2026, but oversupply fears drove Goldman to cut its 2026 Brent average forecast to $68 (from $73).",
            "tone": "bearish",
        },
    ],
}


def get_market_data(tickers: list[str]) -> dict:
    """Return market data for the requested tickers."""
    return {t: MARKET_DATA.get(t.upper(), {"error": "ticker not in coverage"}) for t in tickers}


def get_news(tickers: list[str]) -> dict:
    """Return news headlines for the requested tickers."""
    return {t: NEWS.get(t.upper(), []) for t in tickers}


SUPPORTED_TICKERS = list(MARKET_DATA.keys())
