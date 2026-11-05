import pytest

from demo import run_demo
from metrics import portfolio_metrics


def test_weighted_beta_and_sector_rollup():
    # AAPL beta 1.21, JPM beta 1.06
    metrics = portfolio_metrics({"AAPL": 0.75, "JPM": 0.25})

    assert metrics["portfolio_beta"] == pytest.approx(0.75 * 1.21 + 0.25 * 1.06, abs=0.005)
    assert metrics["sector_weights"] == {"Information Technology": 0.75, "Financials": 0.25}
    assert metrics["top_positions"][0] == {"ticker": "AAPL", "weight": 0.75}


def test_sectors_add_up_across_names():
    metrics = portfolio_metrics({"AAPL": 0.3, "MSFT": 0.3, "NVDA": 0.4})

    assert metrics["sector_weights"] == {"Information Technology": 1.0}


def test_uncovered_names_are_reported_and_excluded_from_beta():
    metrics = portfolio_metrics({"AAPL": 0.5, "ZZZZ": 0.5})

    assert metrics["uncovered_tickers"] == ["ZZZZ"]
    assert metrics["covered_weight"] == 0.5
    assert metrics["portfolio_beta"] == 1.21


def test_largest_beta_contributor_is_not_just_the_largest_position():
    # AAPL is the bigger position (0.4 x 1.21 = 0.48), but NVDA adds more beta (0.3 x 1.78 = 0.53).
    metrics = portfolio_metrics({"AAPL": 0.4, "MSFT": 0.3, "NVDA": 0.3})

    assert metrics["top_positions"][0]["ticker"] == "AAPL"
    assert metrics["largest_beta_contributor"] == "NVDA"


def test_portfolio_with_nothing_in_coverage():
    metrics = portfolio_metrics({"ZZZZ": 1.0})

    assert metrics["portfolio_beta"] is None
    assert metrics["largest_beta_contributor"] is None


def test_demo_memo_admits_it_did_not_read_the_question():
    assert "No model read your question" in run_demo({"AAPL": 1.0})["memo"]


def test_demo_trace_has_the_shape_the_ui_renders():
    trace = run_demo({"AAPL": 0.5, "XOM": 0.5})["trace"]

    assert [t["kind"] for t in trace] == ["tool_call", "tool_result"] * 3
    assert "China" not in trace[3]["text"]  # only the tickers held


def test_demo_names_what_it_left_out():
    assert "ZZZZ" in run_demo({"AAPL": 0.5, "ZZZZ": 0.5})["memo"]


def test_demo_with_nothing_in_coverage_says_so():
    result = run_demo({"ZZZZ": 1.0})

    assert "ZZZZ" in result["memo"]
    assert result["trace"] == []
