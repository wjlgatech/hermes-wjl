"""Conformance tests for the AG-UI adapter — verifies DESIGN.md §7 assertions.

These use an INJECTED fake agent (no real LLM / provider / quota): the fake fires
the same callbacks a real AIAgent fires, so this exercises the actual protocol
translation code in events.py + server.py deterministically.

Run:  python -m pytest agui_adapter/test_conformance.py -v
  or:  python agui_adapter/test_conformance.py   (standalone, prints PASS/FAIL table)
"""

from __future__ import annotations

import json
from typing import Any, List


# --- Fake AIAgent ---------------------------------------------------------
class FakeAgent:
    """Mimics the AIAgent surface the adapter touches."""

    def __init__(self, script: str = "text", history_sink: list | None = None):
        self.stream_delta_callback = None
        self.tool_start_callback = None
        self.tool_complete_callback = None
        self._script = script
        self._history_sink = history_sink

    def run_conversation(self, user_message: str, conversation_history: list, task_id: str) -> dict:
        if self._history_sink is not None:
            self._history_sink.append(len(conversation_history or []))
        if self._script == "raise":
            raise RuntimeError("boom")
        if self._script in ("text", "tool"):
            for piece in ("Hello", ", ", "world"):
                self.stream_delta_callback(piece)
            self.stream_delta_callback(None)
        if self._script == "tool":
            self.tool_start_callback("tc_1", "web_search", {"q": "hermes"})
            self.tool_complete_callback("tc_1", "web_search", {"q": "hermes"}, "a result")
        new_history = list(conversation_history or []) + [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": "Hello, world"},
        ]
        return {"final_response": "Hello, world", "messages": new_history}


def _make_client(script: str = "text", history_sink: list | None = None):
    from fastapi.testclient import TestClient
    from agui_adapter.server import build_app
    from agui_adapter.session import SessionStore

    store = SessionStore(agent_factory=lambda tid: FakeAgent(script, history_sink))
    return TestClient(build_app(session_store=store))


def _post(client, thread="t1", run="r1", text="say hi"):
    payload = {
        "threadId": thread, "runId": run,
        "messages": [{"id": "m1", "role": "user", "content": text}],
        "tools": [], "context": [], "state": {},
    }
    r = client.post("/", json=payload, headers={"accept": "text/event-stream"})
    return r


def _event_types(sse_text: str) -> List[str]:
    types = []
    for line in sse_text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            try:
                types.append(json.loads(line[5:].strip()).get("type"))
            except Exception:
                pass
    return types


# --- The checks (return (id, ok, detail)) ---------------------------------
def check_imports():
    from agui_adapter.server import build_app  # C1
    import ag_ui.core, ag_ui.encoder           # C2  # noqa: F401
    return [("C1 import build_app", True, ""), ("C2 ag_ui importable", True, "")]


def check_basic_stream():
    c = _make_client("text")
    r = _post(c)
    ok_ct = r.headers.get("content-type", "").startswith("text/event-stream")
    types = _event_types(r.text)
    return [
        ("C3 200 + event-stream", r.status_code == 200 and ok_ct, f"{r.status_code} {r.headers.get('content-type')}"),
        ("C4 RUN_STARTED..RUN_FINISHED", types[:1] == ["RUN_STARTED"] and types[-1:] == ["RUN_FINISHED"], str(types)),
        ("C5 text content streamed", "TEXT_MESSAGE_CONTENT" in types, str(types)),
    ]


def check_tool_stream():
    c = _make_client("tool")
    types = _event_types(_post(c).text)
    ok = all(t in types for t in ("TOOL_CALL_START", "TOOL_CALL_ARGS", "TOOL_CALL_END", "TOOL_CALL_RESULT"))
    return [("C6 tool-call events", ok, str(types))]


def check_error():
    c = _make_client("raise")
    types = _event_types(_post(c).text)
    return [("C7 RUN_ERROR on failure", "RUN_ERROR" in types and "RUN_FINISHED" not in types, str(types))]


def check_thread_memory():
    sink: list = []
    c = _make_client("text", history_sink=sink)
    _post(c, thread="mem", run="r1", text="first")
    _post(c, thread="mem", run="r2", text="second")
    # 2nd run should see the 1st run's appended history (non-zero, growing).
    ok = len(sink) == 2 and sink[0] == 0 and sink[1] > 0
    return [("C8 thread memory persists", ok, f"history lengths seen: {sink}")]


def check_cors_and_empty():
    c = _make_client("text")
    opt = c.options("/", headers={
        "origin": "http://localhost:3000",
        "access-control-request-method": "POST",
    })
    cors_ok = opt.status_code in (200, 204) and "access-control-allow-origin" in {k.lower() for k in opt.headers}
    # empty message -> clean run (no 500)
    r = _post(c, thread="empty", text="   ")
    types = _event_types(r.text)
    empty_ok = r.status_code == 200 and types[-1:] == ["RUN_FINISHED"]
    return [
        ("C10 CORS preflight", cors_ok, f"{opt.status_code} {dict(opt.headers).get('access-control-allow-origin')}"),
        ("C11 empty message graceful", empty_ok, str(types)),
    ]


ALL_CHECKS = [
    check_imports, check_basic_stream, check_tool_stream,
    check_error, check_thread_memory, check_cors_and_empty,
]


def run_all():
    rows = []
    for fn in ALL_CHECKS:
        try:
            rows.extend(fn())
        except Exception as e:  # a thrown check = fail
            rows.append((fn.__name__, False, f"EXC {type(e).__name__}: {e}"))
    return rows


# pytest entry points
def test_conformance():
    rows = run_all()
    failures = [r for r in rows if not r[1]]
    assert not failures, "Conformance failures: " + "; ".join(f"{r[0]} ({r[2]})" for r in failures)


if __name__ == "__main__":
    rows = run_all()
    width = max(len(r[0]) for r in rows)
    passed = 0
    for cid, ok, detail in rows:
        mark = "PASS" if ok else "FAIL"
        passed += ok
        print(f"  [{mark}] {cid.ljust(width)}  {detail if not ok else ''}".rstrip())
    print(f"\n{passed}/{len(rows)} checks passed")
    raise SystemExit(0 if passed == len(rows) else 1)
