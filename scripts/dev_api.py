"""Serves api/analyze.py locally, since `next dev` doesn't run Python functions."""

import os
import sys
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from analyze import handler  # noqa: E402

PORT = 8000

if __name__ == "__main__":
    mode = "Claude" if os.environ.get("ANTHROPIC_API_KEY") else "demo mode (no API key)"
    print(f"API on http://127.0.0.1:{PORT}/api/analyze, {mode}")
    ThreadingHTTPServer(("127.0.0.1", PORT), handler).serve_forever()
