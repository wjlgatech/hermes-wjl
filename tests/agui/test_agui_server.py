"""End-to-end tests for the AG-UI adapter (agui_adapter).

Drives the FastAPI app with a fake AIAgent (no LLM) and asserts the SSE stream
carries the correct AG-UI event sequence. Skipped unless the optional `[agui]`
deps (ag-ui-protocol, fastapi, httpx) are installed.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("ag_ui.core")
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from agui_adapter.server import create_app  # noqa: E402
from agui_adapter.session import SessionManager  # noqa: E402


class _FakeAgent:
    """Mimics run_agent.AIAgent's streaming-callback contract."""

    def __init__(self) -> None:
        self.message_callback = None
        self.tool_progress_callback = None
        self.step_callback = None
        self.thinking_callback = None

    def run_conversation(self, user_message, conversation_history, task_id):
        self.message_callback("Let me check. ")
        self.tool_progress_callback("tool.started", name="web_search", args={"q": user_message})
        self.step_callback(1, [{"name": "web_search", "result": "42 results"}])
        self.message_callback("The answer is 42.")
        return {
            "final_response": "The answer is 42.",
            "messages": [{"role": "assistant", "content": "The answer is 42."}],
        }


def _client() -> TestClient:
    sm = SessionManager(agent_factory=lambda thread_id: _FakeAgent())
    return TestClient(create_app(sm))


def _run(client: TestClient, text: str) -> list[dict]:
    body = {
        "threadId": "t1",
        "runId": "r1",
        "messages": [{"id": "m1", "role": "user", "content": text}],
        "tools": [],
        "context": [],
        "state": {},
        "forwardedProps": {},
    }
    events: list[dict] = []
    with client.stream("POST", "/", json=body) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        for line in resp.iter_lines():
            if line and line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


def test_health() -> None:
    assert _client().get("/health").json()["protocol"] == "ag-ui"


def test_full_event_sequence() -> None:
    events = _run(_client(), "what is the answer")
    types = [e["type"] for e in events]
    assert types == [
        "RUN_STARTED",
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "TEXT_MESSAGE_END",
        "TOOL_CALL_START",
        "TOOL_CALL_ARGS",
        "TOOL_CALL_END",
        "TOOL_CALL_RESULT",
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "TEXT_MESSAGE_END",
        "RUN_FINISHED",
    ]
    # tool call carries name + json args; result is matched back to it
    start = next(e for e in events if e["type"] == "TOOL_CALL_START")
    args = next(e for e in events if e["type"] == "TOOL_CALL_ARGS")
    result = next(e for e in events if e["type"] == "TOOL_CALL_RESULT")
    assert start["toolCallName"] == "web_search"
    assert json.loads(args["delta"]) == {"q": "what is the answer"}
    assert result["toolCallId"] == start["toolCallId"]
    assert result["content"] == "42 results"


def test_empty_user_message_still_closes_run() -> None:
    body = {
        "threadId": "t2",
        "runId": "r2",
        "messages": [],
        "tools": [],
        "context": [],
        "state": {},
        "forwardedProps": {},
    }
    with TestClient(create_app(SessionManager(agent_factory=lambda t: _FakeAgent()))).stream(
        "POST", "/", json=body
    ) as resp:
        types = [
            json.loads(line[6:])["type"]
            for line in resp.iter_lines()
            if line and line.startswith("data: ")
        ]
    assert types == ["RUN_STARTED", "RUN_FINISHED"]
