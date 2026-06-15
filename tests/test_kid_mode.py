"""U4 — locked-down kid mode.

Verifies (1) the ``safe`` toolset the kid profile pins really resolves to a
minimal, non-risky tool set, and (2) the kid profile template encodes that
lockdown plus a child-appropriate persona. The allowlist is the authoritative
restriction (see templates/kid-profile/config.yaml); a denylist alone leaks
execute_code/delegate_task, so this asserts the allowlist behavior directly.
"""

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KID_DIR = PROJECT_ROOT / "templates" / "kid-profile"

# Tools a 10-year-old must not have unsupervised access to.
RISKY_TOOLS = {
    "terminal", "process", "read_terminal",
    "write_file", "patch", "read_file", "search_files",
    "execute_code", "delegate_task",
    "cronjob", "send_message",
    "browser_navigate", "browser_click", "browser_type",
    "computer_use",
}
SAFE_EXPECTED = {"web_search", "web_extract", "vision_analyze", "image_generate"}


def _tool_names(defs):
    return {d["function"]["name"] for d in defs}


def test_safe_toolset_is_minimal_and_excludes_risky_tools():
    """The 'safe' allowlist must resolve to only safe tools — no shell, file,
    browser, code-exec, delegation, cron, or messaging. The exact membership of
    the safe set depends on which web/vision providers are available, so assert
    the invariant (subset of safe, zero risky), not an exact count."""
    from model_tools import get_tool_definitions

    names = _tool_names(get_tool_definitions(enabled_toolsets=["safe"], quiet_mode=True))
    assert names, "'safe' toolset resolved to nothing — lockdown would be broken"
    extra = names - SAFE_EXPECTED
    assert not extra, f"'safe' toolset gained unexpected tools: {sorted(extra)}"
    leaked = names & RISKY_TOOLS
    assert not leaked, f"risky tools leaked into 'safe': {sorted(leaked)}"


def test_kid_config_locks_every_platform_to_safe_and_sets_persona():
    cfg = yaml.safe_load((KID_DIR / "config.yaml").read_text())

    # Desktop GUI uses the cli platform key; every platform is pinned to safe.
    platform_toolsets = cfg["platform_toolsets"]
    assert platform_toolsets["cli"] == ["safe"]
    for platform, toolsets in platform_toolsets.items():
        assert toolsets == ["safe"], f"{platform} not locked to safe: {toolsets}"

    # Child persona is defined and active.
    assert cfg["display"]["personality"] == "kid"
    assert "kid" in cfg["agent"]["personalities"]

    # Conversations are bounded.
    assert 0 < cfg["agent"]["max_turns"] <= 30

    # The seed ships no live model/credential — kid-setup fills it later.
    assert not cfg.get("model")


def test_kid_soul_is_present_and_child_appropriate():
    soul = (KID_DIR / "SOUL.md").read_text()
    assert soul.strip(), "SOUL.md is empty"
    low = soul.lower()
    assert "kid" in low or "child" in low
    assert any(word in low for word in ("parent", "grown-up", "grownup", "safe"))
