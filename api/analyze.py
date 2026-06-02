"""Vercel serverless handler — POST /api/analyze with {query, holdings}."""

import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler

# Make sibling modules importable on Vercel (api/ is the cwd at runtime)
sys.path.insert(0, os.path.dirname(__file__))

from agents import run_lead  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 — Vercel runtime requires this name
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw.decode("utf-8") or "{}")
            query = (body.get("query") or "").strip()
            holdings = body.get("holdings") or {}

            if not query:
                return self._json(400, {"error": "missing 'query'"})
            if not isinstance(holdings, dict) or not holdings:
                return self._json(400, {"error": "missing or empty 'holdings'"})

            # Normalize tickers to uppercase, coerce weights to float
            holdings = {str(k).upper(): float(v) for k, v in holdings.items()}

            result = run_lead(query, holdings)
            return self._json(200, result)

        except Exception as e:
            return self._json(
                500,
                {"error": str(e), "trace": traceback.format_exc()},
            )

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def _json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
