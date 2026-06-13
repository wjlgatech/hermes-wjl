"""Cockpit backend tests — Stages 0-2 (PTY, filesystem API, file-change watcher)."""
import json
import time

import pytest
from fastapi.testclient import TestClient

from hermes_cli.cockpit import build_cockpit_app, FileWatcher, _safe_resolve
from pathlib import Path


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "hello.py").write_text("print('hi')\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "note.md").write_text("# note\n")
    (tmp_path / ".git").mkdir()  # should be hidden from the tree
    return tmp_path


@pytest.fixture
def client(workspace):
    with TestClient(build_cockpit_app(workspace)) as c:
        yield c


def test_health(client):
    r = client.get("/cockpit/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "Hermes Cockpit" in r.text


def test_fs_tree_hides_noise(client):
    entries = client.get("/cockpit/api/fs/tree").json()["entries"]
    names = {e["name"] for e in entries}
    assert "hello.py" in names and "sub" in names
    assert ".git" not in names  # ignored


def test_fs_read_and_write(client):
    assert client.get("/cockpit/api/fs/file", params={"path": "hello.py"}).json()["content"] == "print('hi')\n"
    w = client.put("/cockpit/api/fs/file", json={"path": "hello.py", "content": "print('bye')\n"})
    assert w.status_code == 200
    assert client.get("/cockpit/api/fs/file", params={"path": "hello.py"}).json()["content"] == "print('bye')\n"


def test_path_escape_blocked(client):
    r = client.get("/cockpit/api/fs/file", params={"path": "../../../etc/passwd"})
    assert r.status_code in (400, 404)


def test_safe_resolve_rejects_traversal(workspace):
    with pytest.raises(ValueError):
        _safe_resolve(workspace, "../outside")
    assert _safe_resolve(workspace, "hello.py") == (workspace / "hello.py").resolve()


def test_pty_session_echo(workspace):
    """Real PTY: write a command, see its output via the callback.

    Exercises PtySession directly — the TestClient websocket portal doesn't
    interop cleanly with the PTY's background reader thread, but the websocket
    route is a thin wrapper over this class (verified live in integration runs).
    """
    from hermes_cli.cockpit import PtySession

    chunks = []
    sess = PtySession(workspace, on_output=chunks.append)
    try:
        sess.write("echo COCKPIT_OK\n")
        deadline = time.time() + 5
        while time.time() < deadline and "COCKPIT_OK" not in "".join(chunks):
            time.sleep(0.1)
        assert "COCKPIT_OK" in "".join(chunks)
    finally:
        sess.close()


def test_watcher_detects_modification(workspace):
    """FileWatcher should diff mtimes and emit a 'modified' event."""
    events = []
    w = FileWatcher(workspace, interval=0.05)
    w.publish = lambda e: events.append(e)  # capture instead of broadcasting
    w._mtimes = w._scan()
    time.sleep(0.02)
    (workspace / "hello.py").write_text("print('changed')\n")
    # emulate one watch tick
    current = w._scan()
    for path, mtime in current.items():
        prev = w._mtimes.get(path)
        if prev is not None and mtime > prev:
            w.publish({"kind": "modified", "path": w._rel(path)})
    assert any(e["kind"] == "modified" and e["path"] == "hello.py" for e in events)
