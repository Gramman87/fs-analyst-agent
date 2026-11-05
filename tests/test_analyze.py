import json
import math
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import analyze as analyze_module
from analyze import InvalidRequest, handler, parse_request

VALID = {"query": "Am I too concentrated?", "holdings": {"aapl": 0.5, "XOM": 0.5}}


def test_parse_normalizes_tickers_and_trims_the_query():
    query, holdings = parse_request({**VALID, "query": "  hi  "})

    assert query == "hi"
    assert holdings == {"AAPL": 0.5, "XOM": 0.5}


@pytest.mark.parametrize(
    "body",
    [
        [],
        {},
        {"query": "   ", "holdings": {"AAPL": 1}},
        {"query": 7, "holdings": {"AAPL": 1}},
        {"query": "x" * 1001, "holdings": {"AAPL": 1}},
        {"query": "q"},
        {"query": "q", "holdings": {}},
        {"query": "q", "holdings": [1]},
        {"query": "q", "holdings": {"AAPL": "abc"}},
        {"query": "q", "holdings": {"AAPL": True}},
        {"query": "q", "holdings": {"AAPL": math.nan}},
        {"query": "q", "holdings": {"AAPL": math.inf}},
        {"query": "q", "holdings": {"AAPL": 1.5, "XOM": -0.5}},
        {"query": "q", "holdings": {"AAPL": 0.5}},
        {"query": "q", "holdings": {"not a ticker!": 1}},
        {"query": "q", "holdings": {f"T{chr(65 + i // 26)}{chr(65 + i % 26)}": 1 / 21 for i in range(21)}},
    ],
)
def test_parse_rejects(body):
    with pytest.raises(InvalidRequest):
        parse_request(body)


@pytest.fixture
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}/api/analyze"
    httpd.shutdown()
    httpd.server_close()


def post(url, data: bytes):
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def test_serves_a_demo_memo_with_no_key(server):
    status, body = post(server, json.dumps(VALID).encode())

    assert status == 200
    assert body["engine"] == "demo"
    assert body["memo"]


def test_bad_input_is_a_400_with_no_internals(server):
    status, body = post(server, json.dumps({"query": "q", "holdings": {"AAPL": "abc"}}).encode())

    assert status == 400
    assert "trace" not in body


def test_invalid_json_is_a_400(server):
    assert post(server, b"{nope")[0] == 400


def test_invalid_utf8_is_a_400(server):
    assert post(server, b"\xff\xfe")[0] == 400


def test_oversized_body_is_a_413(server):
    assert post(server, b"x" * (64 * 1024 + 1))[0] == 413


def test_unexpected_failure_hides_the_details(server, monkeypatch):
    def explode(query, holdings):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(analyze_module, "analyze", explode)

    status, body = post(server, json.dumps(VALID).encode())

    assert status == 500
    assert body == {"error": "the analysis failed"}
