from datetime import date

import httpx2
import pytest
from conftest import message, text

import engine

HOLDINGS = {"AAPL": 0.5, "XOM": 0.5}


def test_no_key_uses_the_demo_engine_and_says_so():
    result = engine.analyze("q", HOLDINGS)

    assert result["engine"] == "demo"
    assert "no API key" in result["notice"]
    assert "rule-based" in result["memo"]


def test_claude_answer_is_labelled_claude(api):
    api.lead_replies = [message("end_turn", text("The memo."))]

    result = engine.analyze("q", HOLDINGS)

    assert (result["engine"], result["notice"], result["memo"]) == ("claude", None, "The memo.")


@pytest.mark.parametrize(
    "reply",
    [
        500,
        401,  # a bad or revoked key
        400,  # what running out of credits looks like
        429,
        httpx2.ReadTimeout("slow"),
        httpx2.ConnectError("down"),
        message("refusal"),
        message("max_tokens", text("Half a mem")),
    ],
)
def test_any_lead_failure_falls_back_to_a_labelled_demo(api, reply):
    api.lead_replies = [reply]

    result = engine.analyze("q", HOLDINGS)

    assert result["engine"] == "demo"
    assert "unavailable" in result["notice"]
    assert "Half a mem" not in result["memo"]


def test_exhausted_budget_never_calls_the_api(api, monkeypatch):
    monkeypatch.setattr(engine, "budget", engine.DailyBudget(1))
    api.lead_replies = [message("end_turn", text("The memo."))]
    engine.analyze("q", HOLDINGS)
    calls = len(api.requests)

    result = engine.analyze("q", HOLDINGS)

    assert result["engine"] == "demo"
    assert "budget" in result["notice"]
    assert len(api.requests) == calls


def test_budget_resets_the_next_day():
    day = [date(2026, 11, 2)]
    budget = engine.DailyBudget(1, today=lambda: day[0])

    assert budget.try_acquire() is True
    assert budget.try_acquire() is False
    day[0] = date(2026, 11, 3)
    assert budget.try_acquire() is True
