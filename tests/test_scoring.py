import json

from scoring import case_passed, check_coverage, check_routing, parse_judge, unsupported_figures

GOOD_JUDGE = {"accuracy": 4, "specificity": 3, "decisiveness": 5, "critique": "Fine."}
PASSING = {"routing_pass": True, "coverage_pass": True, "judge": GOOD_JUDGE}


def test_routing_allows_extra_calls():
    assert check_routing({"a", "b"}, {"a"}) is True
    assert check_routing({"a"}, {"a", "b"}) is False


def test_coverage_needs_whole_words():
    # All of these slipped through the old substring check.
    assert check_coverage("Corporate bonds generate income.", ["rate"]) == ["rate"]
    assert check_coverage("Biotechnology leads.", ["tech"]) == ["tech"]


def test_coverage_accepts_plurals_case_and_alternatives():
    assert check_coverage("Rates are rising in TECH.", ["rate", "tech"]) == []
    assert check_coverage("Technology leads.", ["tech|technology"]) == []


def test_parse_judge_accepts_valid_scores():
    assert parse_judge(json.dumps(GOOD_JUDGE)) == GOOD_JUDGE


def test_parse_judge_reports_unreadable_replies():
    assert "judge_error" in parse_judge("Sure! Here you go")
    assert "judge_error" in parse_judge("[1, 2]")
    assert "judge_error" in parse_judge(json.dumps({**GOOD_JUDGE, "accuracy": 9}))
    assert "judge_error" in parse_judge(json.dumps({**GOOD_JUDGE, "accuracy": True}))
    assert "judge_error" in parse_judge(json.dumps({"accuracy": 3}))


def test_case_passes_only_when_every_check_does():
    assert case_passed(PASSING) is True
    assert case_passed({**PASSING, "routing_pass": False}) is False
    assert case_passed({**PASSING, "coverage_pass": False}) is False
    assert case_passed({"id": "x", "error": "boom"}) is False
    assert case_passed({**PASSING, "judge": {"judge_error": "bad"}}) is False
    assert case_passed({**PASSING, "judge": {**GOOD_JUDGE, "accuracy": 2}}) is False


def test_unsupported_figures_flags_only_unsourced_numbers():
    memo = "NVDA trades at 64.5 times earnings, with a target of 412.75 and 30% of the book."
    briefings = ["NVDA P/E 64.50"]

    assert unsupported_figures(memo, briefings, {"NVDA": 0.3}) == ["412.75"]


def test_unsupported_figures_ignores_small_integers():
    assert unsupported_figures("There are 3 risks.", [], {}) == []


def test_eval_scores_a_case_end_to_end(api):
    import run_eval
    from conftest import message, text, tool

    case = {
        "id": "c",
        "query": "q",
        "holdings": {"NVDA": 1.0},
        "expected_tools": {"query_news_sentiment"},
        "must_mention": ["NVDA"],
    }
    judge_requests = []

    def reply(request):
        if request["model"] == run_eval.JUDGE_MODEL:
            judge_requests.append(request)
            return message("end_turn", text(json.dumps(GOOD_JUDGE)))
        return message("end_turn", text("NVDA headlines."))

    api.subagent_reply = reply
    api.lead_replies = [
        message("tool_use", tool("t1", "query_news_sentiment", {"tickers": ["NVDA"]})),
        message("end_turn", text("NVDA at 999.5.")),
    ]

    result = run_eval.score_one(case)

    assert case_passed(result) is True
    assert result["unsupported_figures"] == ["999.5"]
    assert judge_requests[0]["output_config"]["format"]["type"] == "json_schema"
    assert "NVDA headlines." in judge_requests[0]["messages"][0]["content"]
