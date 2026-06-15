"""U1 — fork identity guard.

Locks in that the install/clone/update paths point at this fork
(wjlgatech/hermes-wjl) and not upstream. Upstream references that legitimately
add NousResearch as an `upstream` remote are intentionally NOT checked here — see
branding/fork-identity.md for the override sites and the deliberate exclusions.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FORK = "wjlgatech/hermes-wjl"
UPSTREAM_CLONE = "NousResearch/hermes-agent"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text()


def test_install_sh_clones_from_fork():
    s = _read("scripts/install.sh")
    assert 'REPO_URL_HTTPS="https://github.com/wjlgatech/hermes-wjl.git"' in s
    assert 'REPO_URL_SSH="git@github.com:wjlgatech/hermes-wjl.git"' in s
    # The clone constants must not still be the upstream repo.
    assert f'REPO_URL_HTTPS="https://github.com/{UPSTREAM_CLONE}.git"' not in s


def test_install_ps1_clones_and_archives_from_fork():
    s = _read("scripts/install.ps1")
    assert '$RepoUrlHttps = "https://github.com/wjlgatech/hermes-wjl.git"' in s
    # No archive URL should still point at upstream.
    assert f"github.com/{UPSTREAM_CLONE}/archive" not in s


def test_bootstrap_installer_fetches_scripts_from_fork():
    s = _read("apps/bootstrap-installer/src-tauri/src/install_script.rs")
    assert "raw.githubusercontent.com/wjlgatech/hermes-wjl" in s
    assert f"raw.githubusercontent.com/{UPSTREAM_CLONE}" not in s


def test_desktop_update_check_targets_fork():
    s = _read("apps/desktop/electron/update-remote.cjs")
    assert "OFFICIAL_REPO_HTTPS_URL = 'https://github.com/wjlgatech/hermes-wjl.git'" in s
    assert "OFFICIAL_REPO_CANONICAL = 'github.com/wjlgatech/hermes-wjl'" in s


def test_cli_official_repo_is_fork():
    s = _read("hermes_cli/main.py")
    assert 'OFFICIAL_REPO_URL = "https://github.com/wjlgatech/hermes-wjl.git"' in s
    assert f"github.com/{UPSTREAM_CLONE}/archive" not in s


def test_fork_identity_doc_exists():
    doc = _read("branding/fork-identity.md")
    assert FORK in doc
    assert "fork-override" in doc
