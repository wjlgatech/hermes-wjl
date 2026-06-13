"""Entry point for ``hermes agui`` — boots the AG-UI server with uvicorn.

Contract (matches agui_adapter/README.md + the `hermes agui` CLI):
    host : --host  / $HERMES_AGUI_HOST       (default 127.0.0.1)
    port : --port  / $HERMES_AGUI_PORT        (default 9100)
    cors : --allow-origins / $HERMES_AGUI_ALLOW_ORIGINS  (default *)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import List, Optional

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9100


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        prog="hermes agui",
        description="Run Hermes as an AG-UI agent backend for CopilotKit / AG-UI front ends.",
    )
    parser.add_argument("--host", default=os.getenv("HERMES_AGUI_HOST", DEFAULT_HOST),
                        help=f"Bind host (default: {DEFAULT_HOST}, env HERMES_AGUI_HOST)")
    parser.add_argument("--port", type=int, default=int(os.getenv("HERMES_AGUI_PORT", DEFAULT_PORT)),
                        help=f"Bind port (default: {DEFAULT_PORT}, env HERMES_AGUI_PORT)")
    parser.add_argument("--allow-origins", default=os.getenv("HERMES_AGUI_ALLOW_ORIGINS", "*"),
                        help="Comma-separated CORS origins for browser clients (default: *)")
    parser.add_argument("--log-level", default=os.getenv("HERMES_AGUI_LOG_LEVEL", "info"))
    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    try:
        import uvicorn
        from agui_adapter.server import build_app
    except ImportError as exc:
        print(f"AG-UI dependencies not installed: {exc}", file=sys.stderr)
        print("Install with:  pip install -e '.[agui]'", file=sys.stderr)
        sys.exit(1)

    origins = [o.strip() for o in str(args.allow_origins).split(",") if o.strip()]
    app = build_app(allow_origins=origins)

    print(f"Hermes AG-UI server → http://{args.host}:{args.port}/  (CORS: {origins or ['*']})",
          file=sys.stderr)
    print("Point your CopilotKit runtime / AG-UI HttpAgent at that URL.", file=sys.stderr)
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)


if __name__ == "__main__":
    main()
