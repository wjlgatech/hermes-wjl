"""AG-UI server — a FastAPI app that runs Hermes turns and streams AG-UI events.

A single ``POST /`` endpoint accepts an AG-UI ``RunAgentInput``, runs one Hermes
turn for the request's ``thread_id``, and returns a Server-Sent Events stream of
AG-UI events. Any CopilotKit / AG-UI front end can point its agent URL here.

See DESIGN.md for the protocol mapping and conformance checklist (§7).
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List, Optional

from ag_ui.core import (
    EventType,
    RunAgentInput,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
)
from ag_ui.encoder import EventEncoder
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from agui_adapter.events import CallbackBridge
from agui_adapter.session import SessionStore

logger = logging.getLogger(__name__)

# Hermes' AIAgent.run_conversation is synchronous; run it off the event loop.
_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="agui-agent")


def _latest_user_text(messages: List[Any]) -> str:
    """Extract the most recent user message's text from RunAgentInput.messages."""
    for msg in reversed(messages or []):
        role = getattr(msg, "role", None) or (msg.get("role") if isinstance(msg, dict) else None)
        if role == "user":
            content = getattr(msg, "content", None)
            if content is None and isinstance(msg, dict):
                content = msg.get("content")
            if isinstance(content, list):  # multimodal parts
                content = " ".join(
                    str(getattr(p, "text", "") or (p.get("text", "") if isinstance(p, dict) else ""))
                    for p in content
                )
            return (content or "").strip()
    return ""


def build_app(
    *,
    allow_origins: Optional[List[str]] = None,
    session_store: Optional[SessionStore] = None,
) -> FastAPI:
    """Construct the AG-UI FastAPI app. ``session_store`` is injectable for tests."""
    app = FastAPI(title="Hermes AG-UI Adapter", version="1.0.0")
    store = session_store or SessionStore()

    origins = allow_origins or [o for o in os.getenv("HERMES_AGUI_ALLOW_ORIGINS", "*").split(",") if o]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "agent": "hermes", "protocol": "ag-ui"}

    @app.post("/")
    async def run(request: Request):
        # Lenient parse: AG-UI's RunAgentInput marks several fields required
        # (forwardedProps, tools, context, state). Real CopilotKit clients send
        # them, but we default them so a minimal payload / curl smoke-test works.
        try:
            raw = await request.json()
        except Exception:
            raw = {}
        if not isinstance(raw, dict):
            return JSONResponse(status_code=400, content={"error": "body must be a JSON object"})
        merged = {
            "threadId": "", "runId": "", "state": {}, "messages": [],
            "tools": [], "context": [], "forwardedProps": {}, **raw,
        }
        try:
            input_data = RunAgentInput.model_validate(merged)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(status_code=422, content={"error": f"invalid RunAgentInput: {exc}"})

        encoder = EventEncoder(accept=request.headers.get("accept"))
        thread_id = input_data.thread_id or uuid.uuid4().hex
        run_id = input_data.run_id or uuid.uuid4().hex
        user_text = _latest_user_text(input_data.messages)

        loop = asyncio.get_running_loop()
        queue: "asyncio.Queue" = asyncio.Queue()
        bridge = CallbackBridge(queue, loop)
        entry = store.get_or_create(thread_id)

        def _run_agent() -> dict:
            agent = entry.agent
            agent.stream_delta_callback = bridge.on_stream_delta
            agent.tool_start_callback = bridge.on_tool_start
            agent.tool_complete_callback = bridge.on_tool_complete
            try:
                return agent.run_conversation(
                    user_message=user_text,
                    conversation_history=entry.history,
                    task_id=thread_id,
                )
            except Exception as exc:  # noqa: BLE001 — surfaced as RUN_ERROR
                logger.exception("AG-UI agent error (thread=%s)", thread_id)
                return {"error": str(exc)}
            finally:
                agent.stream_delta_callback = None
                agent.tool_start_callback = None
                agent.tool_complete_callback = None

        async def event_stream():
            yield encoder.encode(
                RunStartedEvent(type=EventType.RUN_STARTED, thread_id=thread_id, run_id=run_id)
            )
            # Serialize concurrent runs on the same thread (DESIGN §6.4).
            await entry.lock.acquire()
            error_msg: Optional[str] = None
            try:
                if not user_text:
                    # Empty input: clean no-op run, no crash (DESIGN §6.2 / C11).
                    yield encoder.encode(
                        RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id=thread_id, run_id=run_id)
                    )
                    return

                run_task = asyncio.ensure_future(loop.run_in_executor(_executor, _run_agent))

                # Stream events as the worker produces them; stop once the run is
                # done AND the queue is drained.
                while True:
                    try:
                        ev = await asyncio.wait_for(queue.get(), timeout=0.1)
                        yield encoder.encode(ev)
                    except asyncio.TimeoutError:
                        if run_task.done():
                            break

                try:
                    result = run_task.result()
                except Exception as exc:  # noqa: BLE001
                    result = {"error": str(exc)}
                error_msg = result.get("error")

                # Drain anything still queued, then finalize (close text / fallback).
                while not queue.empty():
                    yield encoder.encode(queue.get_nowait())
                for ev in bridge.finalize_events(result.get("final_response", "") or ""):
                    yield encoder.encode(ev)

                # Persist conversation memory for this thread (DESIGN C8).
                if result.get("messages"):
                    entry.history = result["messages"]
            finally:
                entry.lock.release()

            if error_msg:
                yield encoder.encode(RunErrorEvent(type=EventType.RUN_ERROR, message=str(error_msg)))
            else:
                yield encoder.encode(
                    RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id=thread_id, run_id=run_id)
                )

        return StreamingResponse(event_stream(), media_type=encoder.get_content_type())

    return app
