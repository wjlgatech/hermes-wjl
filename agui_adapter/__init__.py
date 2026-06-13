"""AG-UI adapter — exposes the Hermes agent over the AG-UI protocol.

AG-UI (https://docs.ag-ui.com) is the open protocol that CopilotKit and other
web/agent front ends use to talk to an agent backend over HTTP + SSE. This
package lets any AG-UI/CopilotKit app use Hermes as its agent.

See DESIGN.md for positioning, use cases, and the conformance checklist.

Entry points:
    hermes agui serve            # start the server
    agui_adapter.server.build_app()   # the FastAPI app factory
"""

from __future__ import annotations

__all__ = ["build_app", "main"]


def build_app(*args, **kwargs):  # lazy re-export (avoids importing FastAPI at pkg import)
    from agui_adapter.server import build_app as _build_app

    return _build_app(*args, **kwargs)


def main(*args, **kwargs):
    from agui_adapter.entry import main as _main

    return _main(*args, **kwargs)
