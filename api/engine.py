"""Chooses who answers a request, and always reports which one did."""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Callable

from anthropic import APIError

from agents import AgentStopped, run_lead
from demo import run_demo

log = logging.getLogger(__name__)

DEFAULT_DAILY_LIMIT = 100

NO_KEY = "Demo mode: no API key is configured, so a rule-based engine wrote this memo."
OVER_BUDGET = "Today's live model budget is used up, so a rule-based engine wrote this memo."
UNAVAILABLE = "The live model is unavailable right now, so a rule-based engine wrote this memo."


class DailyBudget:
    """Caps Claude-backed analyses per UTC day.

    The count is per process, so on serverless it resets on a cold start and each instance keeps its
    own. It limits runaway use. The spending limit on the API key is the real ceiling.
    """

    def __init__(self, limit: int, today: Callable[[], Any] | None = None):
        self.limit = limit
        self._today = today or (lambda: datetime.now(timezone.utc).date())
        self._day: Any = None
        self._used = 0
        self._lock = threading.Lock()

    def try_acquire(self) -> bool:
        with self._lock:
            today = self._today()
            if today != self._day:
                self._day, self._used = today, 0
            if self._used >= self.limit:
                return False
            self._used += 1
            return True


budget = DailyBudget(int(os.environ.get("ANALYZE_DAILY_LIMIT", DEFAULT_DAILY_LIMIT)))


def _demo(holdings: dict[str, float], notice: str) -> dict[str, Any]:
    return {**run_demo(holdings), "engine": "demo", "notice": notice}


def analyze(query: str, holdings: dict[str, float]) -> dict[str, Any]:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _demo(holdings, NO_KEY)
    if not budget.try_acquire():
        return _demo(holdings, OVER_BUDGET)
    try:
        return {**run_lead(query, holdings), "engine": "claude", "notice": None}
    except (APIError, AgentStopped) as e:
        log.warning("Falling back to the demo engine: %s", e)
        return _demo(holdings, UNAVAILABLE)
