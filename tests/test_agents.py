import threading

import pytest
from anthropic import APIStatusError
from conftest import message, text, thinking, tool

import agents

HOLDINGS = {"AAPL": 0.5, "XOM": 0.5}
ALL_THREE = [
    tool("t1", "query_market_data", {"tickers": ["AAPL"]}),
    tool("t2", "query_news_sentiment", {"tickers": ["AAPL"]}),
    tool("t3", "analyze_risk_concentration", {"holdings": HOLDINGS}),
]


def test_returns_memo_without_tools(api):
    api.lead_replies = [message("end_turn", thinking(), text("The memo."))]

    result = agents.run_lead("q", HOLDINGS)

    assert result["memo"] == "The memo."
    assert result["trace"] == [{"kind": "thinking", "text": "plan"}]


def test_tool_round_trip_keeps_the_assistant_turn_and_answers_in_one_message(api):
    api.lead_replies = [
        message("tool_use", thinking(signature="sig-abc"), *ALL_THREE),
        message("end_turn", text("The memo.")),
    ]

    agents.run_lead("q", HOLDINGS)

    second = api.lead_requests()[1]["messages"]
    assert [m["role"] for m in second] == ["user", "assistant", "user"]
    assert second[1]["content"][0]["signature"] == "sig-abc"
    assert [r["tool_use_id"] for r in second[2]["content"]] == ["t1", "t2", "t3"]
    assert all(r["content"] == "A briefing." for r in second[2]["content"])


def test_sub_agents_in_one_turn_run_concurrently(api):
    # Each call waits until all three are in flight, so running them in sequence would time out.
    barrier = threading.Barrier(3, timeout=5)

    def reply(request):
        barrier.wait()
        return message("end_turn", text("A briefing."))

    api.subagent_reply = reply
    api.lead_replies = [message("tool_use", *ALL_THREE), message("end_turn", text("The memo."))]

    result = agents.run_lead("q", HOLDINGS)

    assert [t for t in result["trace"] if t["kind"] == "tool_error"] == []


def test_usage_counts_every_call_in_the_request(api):
    api.lead_replies = [
        message("tool_use", *ALL_THREE, input_tokens=10, output_tokens=1, cache_write=7),
        message("end_turn", text("The memo."), input_tokens=20, output_tokens=2, cache_read=9),
    ]

    usage = agents.run_lead("q", HOLDINGS)["usage"]

    assert usage["input_tokens"] == 10 + 20 + 3 * 100
    assert usage["output_tokens"] == 1 + 2 + 3 * 50
    assert usage["cache_creation_input_tokens"] == 7
    assert usage["cache_read_input_tokens"] == 9
    assert (usage["lead_calls"], usage["subagent_calls"]) == (2, 3)


def test_unknown_tool_goes_back_to_the_lead_as_an_error(api):
    api.lead_replies = [
        message("tool_use", tool("t1", "delete_everything", {})),
        message("end_turn", text("The memo.")),
    ]

    result = agents.run_lead("q", HOLDINGS)

    tool_result = api.lead_requests()[1]["messages"][2]["content"][0]
    assert tool_result["is_error"] is True
    assert "delete_everything" in tool_result["content"]
    assert result["trace"][-1]["kind"] == "tool_error"


def test_malformed_tool_input_goes_back_as_an_error(api):
    api.lead_replies = [
        message("tool_use", tool("t1", "query_market_data", {})),
        message("end_turn", text("The memo.")),
    ]

    agents.run_lead("q", HOLDINGS)

    assert api.lead_requests()[1]["messages"][2]["content"][0]["is_error"] is True
    assert api.subagent_requests() == []


def test_sub_agent_failure_lets_the_lead_continue(api):
    api.subagent_reply = lambda request: 500
    api.lead_replies = [message("tool_use", *ALL_THREE), message("end_turn", text("Partial memo."))]

    result = agents.run_lead("q", HOLDINGS)

    assert result["memo"] == "Partial memo."
    assert sum(t["kind"] == "tool_error" for t in result["trace"]) == 3


def test_sub_agent_refusal_is_a_tool_error(api):
    api.subagent_reply = lambda request: message("refusal")
    api.lead_replies = [message("tool_use", ALL_THREE[0]), message("end_turn", text("The memo."))]

    agents.run_lead("q", HOLDINGS)

    assert api.lead_requests()[1]["messages"][2]["content"][0]["is_error"] is True


def test_requests_carry_the_cache_marker_and_tools(api):
    api.lead_replies = [message("end_turn", text("The memo."))]

    agents.run_lead("q", HOLDINGS)

    request = api.lead_requests()[0]
    assert request["cache_control"] == {"type": "ephemeral"}
    assert [t["name"] for t in request["tools"]] == list(agents.SUBAGENT_DISPATCH)


def test_risk_agent_receives_computed_metrics(api):
    api.lead_replies = [message("tool_use", ALL_THREE[2]), message("end_turn", text("The memo."))]

    agents.run_lead("q", {"AAPL": 0.5, "XOM": 0.5})

    assert '"portfolio_beta"' in api.subagent_requests()[0]["messages"][0]["content"]


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_lead_stopping_early_raises_instead_of_returning_a_fake_memo(api, stop_reason):
    api.lead_replies = [message(stop_reason, text("Half a mem"))]

    with pytest.raises(agents.AgentStopped):
        agents.run_lead("q", HOLDINGS)


def test_turn_cap_stops_a_loop(api):
    api.lead_replies = [message("tool_use", ALL_THREE[0])]

    with pytest.raises(agents.AgentStopped):
        agents.run_lead("q", HOLDINGS)

    assert len(api.lead_requests()) == agents.MAX_LEAD_TURNS


def test_deadline_stops_before_calling_the_api(api):
    api.lead_replies = [message("end_turn", text("The memo."))]

    with pytest.raises(agents.AgentStopped):
        agents.run_lead("q", HOLDINGS, deadline_s=0)

    assert api.requests == []


def test_lead_api_failure_propagates(api):
    api.lead_replies = [500]

    with pytest.raises(APIStatusError):
        agents.run_lead("q", HOLDINGS)
