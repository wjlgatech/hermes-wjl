"""Translator — maps Hermes AIAgent callbacks to AG-UI protocol events.

The agent runs synchronously in a worker thread and fires callbacks there; the
HTTP server is async. This bridge pushes AG-UI events onto an ``asyncio.Queue``
from the worker thread via ``loop.call_soon_threadsafe`` (same proven pattern as
acp_adapter). The async streamer drains the queue and SSE-encodes each event.

Mapping (DESIGN §5):
    stream_delta_callback(text)         -> TEXT_MESSAGE_START / _CONTENT / _END
    stream_delta_callback(None)         -> close the open text message
    tool_start_callback(id, name, args) -> TOOL_CALL_START / _ARGS / _END
    tool_complete_callback(id,...,res)  -> TOOL_CALL_RESULT
    (reasoning_callback)                -> deferred to v2 (DESIGN §4)
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, List

from ag_ui.core import (
    EventType,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
)

logger = logging.getLogger(__name__)


def _new_id() -> str:
    return uuid.uuid4().hex


class CallbackBridge:
    """Holds run state and converts agent callbacks into queued AG-UI events."""

    def __init__(self, queue: "asyncio.Queue", loop: asyncio.AbstractEventLoop) -> None:
        self._queue = queue
        self._loop = loop
        self._msg_id: str | None = None   # open assistant text message, if any
        self._any_text = False            # did we stream ANY assistant text?

    # -- thread-safe emit -------------------------------------------------
    def _emit(self, event: Any) -> None:
        """Push an event onto the async queue from the worker thread."""
        self._loop.call_soon_threadsafe(self._queue.put_nowait, event)

    # -- text streaming ---------------------------------------------------
    def on_stream_delta(self, text: Any) -> None:
        # None / empty => end of a text segment: close the open message.
        if not text:
            self._close_text()
            return
        if self._msg_id is None:
            self._msg_id = _new_id()
            self._any_text = True
            self._emit(
                TextMessageStartEvent(
                    type=EventType.TEXT_MESSAGE_START,
                    message_id=self._msg_id,
                    role="assistant",
                )
            )
        self._emit(
            TextMessageContentEvent(
                type=EventType.TEXT_MESSAGE_CONTENT,
                message_id=self._msg_id,
                delta=str(text),
            )
        )

    def _close_text(self) -> None:
        if self._msg_id is not None:
            self._emit(
                TextMessageEndEvent(type=EventType.TEXT_MESSAGE_END, message_id=self._msg_id)
            )
            self._msg_id = None

    # -- tool calls -------------------------------------------------------
    def on_tool_start(self, tool_call_id: Any, name: Any = "", args: Any = None) -> None:
        # A tool call interrupts any open text message; close it first.
        self._close_text()
        tc_id = str(tool_call_id) if tool_call_id is not None else _new_id()
        self._emit(
            ToolCallStartEvent(
                type=EventType.TOOL_CALL_START,
                tool_call_id=tc_id,
                tool_call_name=str(name or "tool"),
            )
        )
        try:
            args_str = args if isinstance(args, str) else json.dumps(args or {})
        except (TypeError, ValueError):
            args_str = json.dumps({"raw": str(args)})
        self._emit(ToolCallArgsEvent(type=EventType.TOOL_CALL_ARGS, tool_call_id=tc_id, delta=args_str))
        self._emit(ToolCallEndEvent(type=EventType.TOOL_CALL_END, tool_call_id=tc_id))

    def on_tool_complete(self, tool_call_id: Any, name: Any = "", args: Any = None, result: Any = None) -> None:
        tc_id = str(tool_call_id) if tool_call_id is not None else _new_id()
        content = result if isinstance(result, str) else json.dumps(result, default=str)
        self._emit(
            ToolCallResultEvent(
                type=EventType.TOOL_CALL_RESULT,
                message_id=_new_id(),
                tool_call_id=tc_id,
                content=content if content is not None else "",
                role="tool",
            )
        )

    # -- finalize (run loop end) -----------------------------------------
    def finalize_events(self, final_response: str = "") -> List[Any]:
        """Closing events: end any open text message, and if NO text streamed
        during the run, emit the final response as one text message (fallback)."""
        events: List[Any] = []
        if self._msg_id is not None:
            events.append(
                TextMessageEndEvent(type=EventType.TEXT_MESSAGE_END, message_id=self._msg_id)
            )
            self._msg_id = None
        if not self._any_text and final_response:
            mid = _new_id()
            events.append(
                TextMessageStartEvent(type=EventType.TEXT_MESSAGE_START, message_id=mid, role="assistant")
            )
            events.append(
                TextMessageContentEvent(type=EventType.TEXT_MESSAGE_CONTENT, message_id=mid, delta=str(final_response))
            )
            events.append(TextMessageEndEvent(type=EventType.TEXT_MESSAGE_END, message_id=mid))
        return events
