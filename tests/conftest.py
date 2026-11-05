"""Runs the real Anthropic SDK against a local transport, so requests are really built and
responses really parsed, with no key and no spend."""

from __future__ import annotations

import json
import threading
from typing import Any, Callable

import httpx2
import pytest
from anthropic import Anthropic, DefaultHttpxClient

import agents
import engine


def thinking(text: str = "plan", signature: str = "sig-1") -> dict:
    return {"type": "thinking", "thinking": text, "signature": signature}


def text(value: str) -> dict:
    return {"type": "text", "text": value}


def tool(tool_id: str, name: str, tool_input: dict) -> dict:
    return {"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}


def message(stop_reason: str, *content: dict, input_tokens: int = 10, output_tokens: int = 5,
            cache_write: int = 0, cache_read: int = 0) -> dict:
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "test-model",
        "content": list(content),
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_creation_input_tokens": cache_write,
            "cache_read_input_tokens": cache_read,
        },
    }


class FakeApi:
    def __init__(self) -> None:
        self.lead_replies: list[Any] = []
        self.subagent_reply: Callable[[dict], Any] = lambda request: message(
            "end_turn", text("A briefing."), input_tokens=100, output_tokens=50
        )
        self.requests: list[dict] = []
        self._lock = threading.Lock()

    def lead_requests(self) -> list[dict]:
        return [r for r in self.requests if r["model"] == agents.LEAD_MODEL]

    def subagent_requests(self) -> list[dict]:
        return [r for r in self.requests if r["model"] == agents.SUBAGENT_MODEL]

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        with self._lock:
            self.requests.append(body)
            if body["model"] == agents.LEAD_MODEL:
                # The last queued reply repeats, for tests of the turn cap.
                reply = self.lead_replies.pop(0) if len(self.lead_replies) > 1 else self.lead_replies[0]
            else:
                reply = None
        if reply is None:
            reply = self.subagent_reply(body)
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, int):
            return httpx2.Response(reply, json={"type": "error", "error": {"type": "api_error", "message": "boom"}})
        return httpx2.Response(200, json=reply)


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> FakeApi:
    fake = FakeApi()
    client = Anthropic(
        api_key="test-key",
        max_retries=0,
        http_client=DefaultHttpxClient(transport=httpx2.MockTransport(fake.handle)),
    )
    monkeypatch.setattr(agents, "_client", client)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(engine, "budget", engine.DailyBudget(100))
    return fake


@pytest.fixture(autouse=True)
def no_real_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must never spend real credits, even with a key in the developer's environment."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(agents, "_client", None)
