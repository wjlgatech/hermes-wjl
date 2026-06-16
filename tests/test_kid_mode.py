"""U4 — kid builder mode.

The kid profile gives a child FULL builder powers (websites/games/code/files/
terminal) — the guardrail is CONTENT, not capability. This verifies the template
(1) enables the full toolset (not the locked-down `safe` set), and (2) carries a
firm content-boundary persona in SOUL.md + config. (The `safe` preset itself is
also checked to stay minimal, since it remains available for callers who want
the locked-down mode.)
"""

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KID_DIR = PROJECT_ROOT / "templates" / "kid-profile"

# The strongest builder powers — with these you can create/run anything. (Other
# file tools may be environment-gated in CI, so assert these two as the proof.)
BUILDER_TOOLS = {"terminal", "execute_code"}
SAFE_EXPECTED = {"web_search", "web_extract", "vision_analyze", "image_generate"}


def _tool_names(defs):
    return {d["function"]["name"] for d in defs}


def test_full_toolset_includes_builder_tools():
    """The `hermes-cli` toolset the kid profile pins must grant real builder
    power — terminal + code execution — and be far broader than `safe`."""
    from model_tools import get_tool_definitions

    full = _tool_names(get_tool_definitions(enabled_toolsets=["hermes-cli"], quiet_mode=True))
    safe = _tool_names(get_tool_definitions(enabled_toolsets=["safe"], quiet_mode=True))
    missing = BUILDER_TOOLS - full
    assert not missing, f"builder power missing from 'hermes-cli': {sorted(missing)}"
    assert len(full) > len(safe), "kid toolset should be broader than the locked-down 'safe' set"


def test_safe_toolset_still_minimal():
    """The `safe` preset remains a minimal, non-risky set (kept available for a
    locked-down mode); the kid profile just doesn't use it anymore."""
    from model_tools import get_tool_definitions

    names = _tool_names(get_tool_definitions(enabled_toolsets=["safe"], quiet_mode=True))
    assert names, "'safe' toolset resolved to nothing"
    assert not (names - SAFE_EXPECTED), f"'safe' gained unexpected tools: {sorted(names - SAFE_EXPECTED)}"


def test_kid_config_uses_full_builder_toolset_and_persona():
    cfg = yaml.safe_load((KID_DIR / "config.yaml").read_text())

    # Full builder toolset on the desktop (cli) platform — NOT the safe lockdown.
    platform_toolsets = cfg["platform_toolsets"]
    assert platform_toolsets["cli"] == ["hermes-cli"]
    assert "safe" not in platform_toolsets["cli"]
    # No capability denylist — builder mode is intentionally unrestricted on tools.
    assert not cfg["agent"].get("disabled_toolsets")

    # Builder/child persona is defined and active.
    assert cfg["display"]["personality"] == "kid"
    assert "kid" in cfg["agent"]["personalities"]
    assert cfg["agent"]["max_turns"] > 0

    # The seed ships no live model/credential — kid-setup fills it later.
    assert not cfg.get("model")


def test_kid_soul_has_content_boundaries():
    soul = (KID_DIR / "SOUL.md").read_text().lower()
    assert soul.strip(), "SOUL.md is empty"
    # Builder identity.
    assert "build" in soul or "code" in soul
    # The firm content guardrail must be present.
    assert "sex" in soul and ("violen" in soul) and ("occult" in soul or "cult" in soul)
    assert "safe" in soul  # safe-search / safe mode
