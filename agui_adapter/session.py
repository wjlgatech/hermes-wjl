"""Session store — maps an AG-UI ``thread_id`` to a Hermes AIAgent + history.

One AG-UI thread == one Hermes conversation. Agents are created lazily on first
use and kept in memory (v1). Each thread carries an asyncio lock so two runs on
the same thread are serialized (no interleaved history corruption — DESIGN §6.4).
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _stderr_print(*args: Any, **kwargs: Any) -> None:
    """Route any incidental agent stdout to stderr (keep responses protocol-clean)."""
    kwargs["file"] = sys.stderr
    print(*args, **kwargs)


@dataclass
class SessionEntry:
    thread_id: str
    agent: Any  # AIAgent
    history: List[Dict[str, Any]] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class SessionStore:
    """Thread-safe (process-local) registry of AG-UI threads → Hermes agents."""

    def __init__(self, agent_factory=None) -> None:
        self._sessions: Dict[str, SessionEntry] = {}
        self._guard = threading.Lock()
        self._agent_factory = agent_factory  # for tests

    def get_or_create(self, thread_id: str) -> SessionEntry:
        with self._guard:
            entry = self._sessions.get(thread_id)
            if entry is None:
                entry = SessionEntry(thread_id=thread_id, agent=self._build_agent(thread_id))
                self._sessions[thread_id] = entry
            return entry

    def reset(self, thread_id: str) -> None:
        with self._guard:
            self._sessions.pop(thread_id, None)

    # ------------------------------------------------------------------
    def _build_agent(self, thread_id: str) -> Any:
        if self._agent_factory is not None:
            return self._agent_factory(thread_id)

        from run_agent import AIAgent
        from hermes_cli.config import load_config
        from hermes_cli.runtime_provider import resolve_runtime_provider

        config = load_config()
        model_cfg = config.get("model")
        default_model = ""
        config_provider = None
        if isinstance(model_cfg, dict):
            default_model = str(model_cfg.get("default") or "")
            config_provider = model_cfg.get("provider")
        elif isinstance(model_cfg, str) and model_cfg.strip():
            default_model = model_cfg.strip()

        kwargs: Dict[str, Any] = {
            "platform": "agui",
            "enabled_toolsets": ["hermes-cli"],
            "quiet_mode": True,
            "session_id": thread_id,
            "model": default_model,
        }
        # Reuse Hermes' configured provider/credentials (free Codex, etc.) — DESIGN C13.
        try:
            runtime = resolve_runtime_provider(requested=config_provider)
            kwargs.update(
                {
                    "provider": runtime.get("provider"),
                    "api_mode": runtime.get("api_mode"),
                    "base_url": runtime.get("base_url"),
                    "api_key": runtime.get("api_key"),
                    "command": runtime.get("command"),
                    "args": list(runtime.get("args") or []),
                }
            )
        except Exception:
            logger.debug("AG-UI session falling back to default provider resolution", exc_info=True)

        agent = AIAgent(**kwargs)
        agent._print_fn = _stderr_print
        return agent
