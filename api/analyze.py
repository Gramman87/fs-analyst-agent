"""Vercel serverless handler: POST /api/analyze with {query, holdings}."""

from __future__ import annotations

import json
import logging
import math
import os
import re
import sys
from http.server import BaseHTTPRequestHandler
from typing import Any

# Make sibling modules importable on Vercel (api/ is the cwd at runtime)
sys.path.insert(0, os.path.dirname(__file__))

from engine import analyze  # noqa: E402

log = logging.getLogger(__name__)

MAX_BODY_BYTES = 64 * 1024
MAX_QUERY_CHARS = 1000
MAX_HOLDINGS = 20
WEIGHT_SUM_TOLERANCE = 0.02
TICKER = re.compile(r"^[A-Z][A-Z.\-]{0,9}$")


class InvalidRequest(ValueError):
    """The message is safe to show the caller."""


def parse_request(body: Any) -> tuple[str, dict[str, float]]:
    """Validate a request body. Every request spends money, so bad ones stop here."""
    if not isinstance(body, dict):
        raise InvalidRequest("body must be a JSON object")

    query = body.get("query")
    if not isinstance(query, str) or not query.strip():
        raise InvalidRequest("missing 'query'")
    if len(query) > MAX_QUERY_CHARS:
        raise InvalidRequest(f"'query' is longer than {MAX_QUERY_CHARS} characters")

    raw = body.get("holdings")
    if not isinstance(raw, dict) or not raw:
        raise InvalidRequest("missing or empty 'holdings'")
    if len(raw) > MAX_HOLDINGS:
        raise InvalidRequest(f"'holdings' has more than {MAX_HOLDINGS} positions")

    holdings: dict[str, float] = {}
    for key, weight in raw.items():
        ticker = str(key).strip().upper()
        if not TICKER.match(ticker):
            raise InvalidRequest(f"invalid ticker: {str(key)[:12]!r}")
        # bool is an int in Python, and json.loads accepts NaN and Infinity.
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight):
            raise InvalidRequest(f"weight for {ticker} must be a number")
        if weight <= 0:
            raise InvalidRequest(f"weight for {ticker} must be positive")
        holdings[ticker] = float(weight)

    total = sum(holdings.values())
    if abs(total - 1) > WEIGHT_SUM_TOLERANCE:
        raise InvalidRequest(f"weights sum to {total:.2f}, not about 1.0")
    return query.strip(), holdings


class handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 (name required by the Vercel runtime)
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._json(400, {"error": "invalid Content-Length"})
        if length > MAX_BODY_BYTES:
            return self._json(413, {"error": "request body is too large"})

        try:
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            query, holdings = parse_request(body)
        except InvalidRequest as e:
            return self._json(400, {"error": str(e)})
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._json(400, {"error": "body must be valid JSON"})

        try:
            return self._json(200, analyze(query, holdings))
        except Exception:
            # Details go to the server log. Tracebacks don't belong in a public response.
            log.exception("analysis failed")
            return self._json(500, {"error": "the analysis failed"})

    def _json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
