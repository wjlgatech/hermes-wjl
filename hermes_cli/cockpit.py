"""Hermes Cockpit — an agent-native IDE surface (Stages 0-2).

A browser cockpit where you *watch Hermes code*: a live PTY terminal, a Monaco
editor + file tree, and a file-change event stream that lights up the editor as
the agent (running in any process) edits files on disk.

This is deliberately self-contained — it serves its own static UI (xterm + Monaco
from CDN) and a small FastAPI surface, so it can ship and be verified without the
Vite/React dashboard build. A later pass folds the UI into ``web/src``.

Surface
-------
- ``GET  /``                      → the cockpit HTML
- ``WS   /cockpit/ws/pty``        → bidirectional real PTY (Stage 0)
- ``GET  /cockpit/api/fs/tree``   → directory listing (Stage 1)
- ``GET  /cockpit/api/fs/file``   → read a file (Stage 1)
- ``PUT  /cockpit/api/fs/file``   → write a file (Stage 1)
- ``GET  /cockpit/api/events``    → SSE stream of file-change events (Stage 2)
- ``GET  /cockpit/api/health``    → liveness/config probe

Run: ``python -m hermes_cli.cockpit --root . --port 9200``  (or ``hermes cockpit``).
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Imported at module scope so endpoint annotations (e.g. ``ws: WebSocket``)
# resolve under ``from __future__ import annotations`` — FastAPI's get_type_hints
# looks in module globals, not the local scope of build_cockpit_app(). Guarded so
# the module still imports for CLI registration when fastapi isn't installed.
try:
    from fastapi import WebSocket
except ImportError:  # pragma: no cover - optional dep ([agui]/[web] extra)
    WebSocket = None  # type: ignore

# ── workspace root (the directory the cockpit operates on) ──────────────────
# Resolved once at app-build time; all FS access is confined under it.
_DEFAULT_ROOT = Path(os.environ.get("HERMES_COCKPIT_ROOT", os.getcwd())).resolve()

# Files/dirs we never surface in the tree (noise + heavy).
_TREE_IGNORE = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "dist", "build", "web_dist", ".direnv",
}
_MAX_FILE_BYTES = 2_000_000  # refuse to open files larger than ~2MB in the editor


def _safe_resolve(root: Path, rel: str) -> Path:
    """Resolve ``rel`` under ``root``, refusing escapes (``..`` traversal)."""
    target = (root / rel.lstrip("/")).resolve() if rel else root
    if target != root and root not in target.parents:
        raise ValueError(f"path escapes workspace root: {rel!r}")
    return target


# ════════════════════════════════════════════════════════════════════════════
# Stage 0 — PTY session
# ════════════════════════════════════════════════════════════════════════════
class PtySession:
    """A single real pseudo-terminal running the user's shell.

    Output is read on a daemon thread and forwarded to ``on_output`` (a plain
    callable that takes a ``str``). Input/resize come from the websocket.
    """

    def __init__(self, root: Path, on_output, shell: Optional[str] = None,
                 cols: int = 80, rows: int = 24) -> None:
        from ptyprocess import PtyProcess  # local import: optional dep

        self._on_output = on_output
        self._alive = True
        shell = shell or os.environ.get("SHELL", "/bin/bash")
        env = dict(os.environ, TERM="xterm-256color", HERMES_COCKPIT="1")
        self._proc = PtyProcess.spawn(
            [shell], dimensions=(rows, cols), cwd=str(root), env=env,
        )
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self) -> None:
        while self._alive:
            try:
                data = self._proc.read(4096)
            except EOFError:
                break
            except Exception:
                break
            if not data:
                break
            text = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data
            try:
                self._on_output(text)
            except Exception:
                pass
        self._alive = False
        try:
            self._on_output("\r\n[cockpit] shell exited\r\n")
        except Exception:
            pass

    def write(self, data: str) -> None:
        if self._alive:
            try:
                self._proc.write(data.encode("utf-8", errors="replace"))
            except Exception:
                self._alive = False

    def resize(self, cols: int, rows: int) -> None:
        if self._alive:
            try:
                self._proc.setwinsize(rows, cols)
            except Exception:
                pass

    @property
    def alive(self) -> bool:
        return self._alive and self._proc.isalive()

    def close(self) -> None:
        self._alive = False
        try:
            self._proc.terminate(force=True)
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════════════
# Stage 3 — shared PTY: named terminals that multiple clients (and the agent)
# attach to, with output fanned out to all. The agent injects commands via the
# HTTP /run endpoint, so its commands + output appear in the same xterm the
# human is watching — and the human can grab the keyboard at any time.
# ════════════════════════════════════════════════════════════════════════════
class SharedPty:
    """One named PTY with output fanned out to N attached subscribers."""

    def __init__(self, root: Path, name: str) -> None:
        self.name = name
        self._subs: Set["asyncio.Queue"] = set()
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._backlog: List[str] = []  # recent output for late-joiners
        self._session = PtySession(root, on_output=self._broadcast)

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def _broadcast(self, text: str) -> None:
        with self._lock:
            self._backlog.append(text)
            if len(self._backlog) > 400:
                self._backlog = self._backlog[-400:]
            subs = list(self._subs)
            loop = self._loop
        if loop is None:
            return
        for q in subs:
            loop.call_soon_threadsafe(q.put_nowait, text)

    def subscribe(self) -> "asyncio.Queue":
        q: asyncio.Queue = asyncio.Queue()
        with self._lock:
            self._subs.add(q)
            backlog = "".join(self._backlog)
        if backlog:
            q.put_nowait(backlog)  # replay so a new tab sees the scrollback
        return q

    def unsubscribe(self, q: "asyncio.Queue") -> None:
        with self._lock:
            self._subs.discard(q)

    def write(self, data: str) -> None:
        self._session.write(data)

    def resize(self, cols: int, rows: int) -> None:
        self._session.resize(cols, rows)

    def run(self, command: str) -> None:
        """Inject a command line (the agent's hands on the shared terminal)."""
        line = command if command.endswith("\n") else command + "\n"
        self._session.write(line)

    @property
    def sub_count(self) -> int:
        with self._lock:
            return len(self._subs)

    def close(self) -> None:
        self._session.close()


class PtyHub:
    """Registry of named SharedPty terminals (default name: ``main``)."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._ptys: Dict[str, SharedPty] = {}
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def get_or_create(self, name: str) -> SharedPty:
        with self._lock:
            sp = self._ptys.get(name)
            if sp is None:
                sp = SharedPty(self._root, name)
                if self._loop is not None:
                    sp.bind_loop(self._loop)
                self._ptys[name] = sp
            return sp

    def get(self, name: str) -> Optional[SharedPty]:
        with self._lock:
            return self._ptys.get(name)

    def names(self) -> List[str]:
        with self._lock:
            return list(self._ptys)

    def close_all(self) -> None:
        with self._lock:
            ptys = list(self._ptys.values())
            self._ptys.clear()
        for sp in ptys:
            sp.close()


# ════════════════════════════════════════════════════════════════════════════
# Stage 2 — file-change event bus (so the editor lights up as the agent edits)
# ════════════════════════════════════════════════════════════════════════════
class FileWatcher:
    """Polls the workspace tree for mtime changes and publishes events.

    Process-agnostic by design: whether the agent edits a file from the gateway,
    a cron job, or a CLI session, the change shows up here. ~400ms cadence keeps
    it responsive without hammering the FS.
    """

    def __init__(self, root: Path, interval: float = 0.4) -> None:
        self._root = root
        self._interval = interval
        self._subscribers: Set["asyncio.Queue"] = set()
        self._lock = threading.Lock()
        self._mtimes: Dict[str, float] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        if self._running:  # idempotent — lazy-start may call this more than once
            self._loop = loop
            return
        self._loop = loop
        self._mtimes = self._scan()  # prime so we only report *changes*
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def subscribe(self) -> "asyncio.Queue":
        q: asyncio.Queue = asyncio.Queue()
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: "asyncio.Queue") -> None:
        with self._lock:
            self._subscribers.discard(q)

    def publish(self, event: Dict[str, Any]) -> None:
        """Thread-safe broadcast to all SSE subscribers."""
        if self._loop is None:
            return
        with self._lock:
            subs = list(self._subscribers)
        for q in subs:
            self._loop.call_soon_threadsafe(q.put_nowait, event)

    def _scan(self) -> Dict[str, float]:
        # Cap the walk so a huge workspace root (e.g. a home dir) can't turn the
        # 400ms poll into a CPU sink. Beyond the cap we stop scanning — the tree
        # still browses fine (that's on-demand), only live-reload is bounded.
        out: Dict[str, float] = {}
        for dirpath, dirnames, filenames in os.walk(self._root):
            dirnames[:] = [d for d in dirnames if d not in _TREE_IGNORE]
            for fn in filenames:
                p = Path(dirpath) / fn
                try:
                    out[str(p)] = p.stat().st_mtime
                except OSError:
                    pass
            if len(out) > 20000:
                break
        return out

    def _watch_loop(self) -> None:
        while self._running:
            time.sleep(self._interval)
            try:
                current = self._scan()
            except Exception:
                continue
            for path, mtime in current.items():
                prev = self._mtimes.get(path)
                if prev is None:
                    self.publish({"kind": "created", "path": self._rel(path)})
                elif mtime > prev:
                    self.publish({"kind": "modified", "path": self._rel(path)})
            for path in self._mtimes:
                if path not in current:
                    self.publish({"kind": "deleted", "path": self._rel(path)})
            self._mtimes = current

    def _rel(self, abspath: str) -> str:
        try:
            return str(Path(abspath).relative_to(self._root))
        except ValueError:
            return abspath


# ════════════════════════════════════════════════════════════════════════════
# FastAPI app
# ════════════════════════════════════════════════════════════════════════════
def build_cockpit_app(root: Optional[Path] = None):
    """Construct the cockpit FastAPI app rooted at ``root`` (default cwd)."""
    from fastapi import FastAPI, WebSocketDisconnect, Query, Body
    from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

    root = (root or _DEFAULT_ROOT).resolve()
    app = FastAPI(title="Hermes Cockpit", docs_url=None, redoc_url=None)
    watcher = FileWatcher(root)
    hub = PtyHub(root)
    _runtime = {"started": False}

    def _ensure_runtime() -> None:
        # Bind the running loop + start the watcher lazily, on first request.
        # When this app is MOUNTED in the dashboard (app.mount), Starlette does
        # not reliably fire its startup event, so we can't rely on it alone.
        if _runtime["started"]:
            return
        loop = asyncio.get_running_loop()
        watcher.start(loop)
        hub.bind_loop(loop)
        _runtime["started"] = True

    @app.on_event("startup")
    async def _startup() -> None:
        _ensure_runtime()

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        watcher.stop()
        hub.close_all()

    # ── Stage 0+3: PTY websocket (named, shared across clients + the agent) ──
    @app.websocket("/cockpit/ws/pty")
    async def pty_ws(ws: WebSocket) -> None:
        await ws.accept()
        _ensure_runtime()
        name = ws.query_params.get("name", "main")
        sp = hub.get_or_create(name)
        out_q = sp.subscribe()

        async def pump_output() -> None:
            try:
                while True:
                    text = await out_q.get()
                    await ws.send_text(json.dumps({"type": "output", "data": text}))
            except Exception:
                pass

        pump = asyncio.create_task(pump_output())
        try:
            while True:
                raw = await ws.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                t = msg.get("type")
                if t == "input":
                    sp.write(msg.get("data", ""))
                elif t == "resize":
                    sp.resize(int(msg.get("cols", 80)), int(msg.get("rows", 24)))
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            sp.unsubscribe(out_q)  # leave the PTY alive for other clients + the agent
            pump.cancel()

    # ── Stage 3: command-inject — the agent's hands on the shared terminal ──
    @app.post("/cockpit/api/pty/{name}/run")
    async def pty_run(name: str, payload: Dict[str, Any] = Body(...)):
        command = (payload.get("command") or "").strip()
        if not command:
            return JSONResponse({"error": "empty command"}, status_code=400)
        sp = hub.get_or_create(name)
        sp.run(command)
        return {"pty": name, "ran": command, "watchers": sp.sub_count}

    @app.get("/cockpit/api/pty")
    async def pty_list():
        return {"ptys": [{"name": n, "watchers": hub.get(n).sub_count} for n in hub.names()]}

    # ── Stage 1: filesystem API ─────────────────────────────────────────────
    @app.get("/cockpit/api/fs/tree")
    async def fs_tree(path: str = Query("")):
        try:
            target = _safe_resolve(root, path)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        if not target.is_dir():
            return JSONResponse({"error": "not a directory"}, status_code=400)
        entries: List[Dict[str, Any]] = []
        for child in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            if child.name in _TREE_IGNORE:
                continue
            entries.append({
                "name": child.name,
                "path": str(child.relative_to(root)),
                "dir": child.is_dir(),
            })
        return {"root": str(root), "path": path, "entries": entries}

    @app.get("/cockpit/api/fs/file")
    async def fs_read(path: str = Query(...)):
        try:
            target = _safe_resolve(root, path)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        if not target.is_file():
            return JSONResponse({"error": "not a file"}, status_code=404)
        if target.stat().st_size > _MAX_FILE_BYTES:
            return JSONResponse({"error": "file too large"}, status_code=413)
        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return JSONResponse({"error": "binary file"}, status_code=415)
        return {"path": path, "content": content}

    @app.put("/cockpit/api/fs/file")
    async def fs_write(payload: Dict[str, Any] = Body(...)):
        path = payload.get("path", "")
        content = payload.get("content", "")
        try:
            target = _safe_resolve(root, path)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"path": path, "bytes": len(content.encode("utf-8"))}

    # ── Stage 2: file-change SSE ────────────────────────────────────────────
    @app.get("/cockpit/api/events")
    async def events():
        _ensure_runtime()
        q = watcher.subscribe()

        async def gen():
            try:
                yield "retry: 2000\n\n"
                while True:
                    try:
                        event = await asyncio.wait_for(q.get(), timeout=15.0)
                        yield f"data: {json.dumps(event)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
            finally:
                watcher.unsubscribe(q)

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.get("/cockpit/api/health")
    async def health():
        return {"status": "ok", "root": str(root), "surface": "cockpit", "stages": "0-3"}

    # ── static UI ────────────────────────────────────────────────────────────
    @app.get("/", response_class=HTMLResponse)
    async def index():
        return _COCKPIT_HTML

    return app


def serve(root: Optional[Path] = None, host: str = "127.0.0.1", port: int = 9200) -> None:
    import uvicorn
    app = build_cockpit_app(root)
    print(f"🛩️  Hermes Cockpit on http://{host}:{port}  (workspace: {root or _DEFAULT_ROOT})")
    uvicorn.run(app, host=host, port=port, log_level="warning")


# The static UI lives in cockpit_static/index.html; inlined at import for a
# zero-file-dependency single module. Loaded lazily to keep import cheap.
def _load_html() -> str:
    here = Path(__file__).parent / "cockpit_static" / "index.html"
    if here.is_file():
        return here.read_text(encoding="utf-8")
    return "<!doctype html><title>Hermes Cockpit</title><h1>cockpit UI missing</h1>"


_COCKPIT_HTML = _load_html()


def main(argv: Optional[List[str]] = None) -> None:
    import argparse
    ap = argparse.ArgumentParser(prog="hermes-cockpit", description="Hermes agent-native IDE cockpit")
    ap.add_argument("--root", default=os.environ.get("HERMES_COCKPIT_ROOT", os.getcwd()))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9200)
    args = ap.parse_args(argv)
    serve(Path(args.root).resolve(), args.host, args.port)


if __name__ == "__main__":
    main()
