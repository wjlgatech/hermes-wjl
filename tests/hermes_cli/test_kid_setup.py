"""U6 — hermes kid-setup orchestrator.

Exercises apply_kid_setup against an isolated HERMES_HOME: it must seed the
builder profile (full toolset + content-boundary persona), set the model, write
the key, copy SOUL.md, and mark the profile active for BOTH the CLI
(~/.hermes/active_profile) and the desktop GUI (its own active-profile.json).
Re-running must be idempotent and re-apply the template.
"""

import json

import yaml


def _load_setup(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    # Isolate the desktop active-profile.json from the real Electron userData dir.
    monkeypatch.setenv("HERMES_DESKTOP_USERDATA", str(tmp_path / "desktop"))
    from hermes_cli import profiles
    from hermes_cli.subcommands import kid_setup
    return kid_setup.apply_kid_setup, profiles, kid_setup


def test_free_mode_seeds_builder_profile_with_model_and_key(monkeypatch, tmp_path):
    apply_kid_setup, profiles, kid_setup = _load_setup(monkeypatch, tmp_path)

    pdir = apply_kid_setup("kid", "free", provider="nvidia", key="nvapi-secret")

    cfg = yaml.safe_load((pdir / "config.yaml").read_text())
    # Builder toolset survived the template -> profile write (NOT the safe lockdown).
    assert cfg["platform_toolsets"]["cli"] == ["hermes-cli"]
    assert cfg["display"]["personality"] == "kid"
    assert "kid" in cfg["agent"]["personalities"]
    # Model configured from the free provider.
    assert cfg["model"]["provider"] == "nvidia"
    assert cfg["model"]["base_url"].startswith("https://integrate.api.nvidia.com")
    # Persona + key landed.
    assert (pdir / "SOUL.md").exists() and (pdir / "SOUL.md").read_text().strip()
    assert "NVIDIA_API_KEY=nvapi-secret" in (pdir / ".env").read_text()
    # Active profile points at the kid — for the CLI...
    assert profiles.get_active_profile() == "kid"
    # ...and for the desktop GUI (its own file, matching main.cjs's format).
    desk = kid_setup.desktop_active_profile_path()
    assert desk.exists()
    assert json.loads(desk.read_text())["profile"] == "kid"


def test_local_mode_uses_ollama_and_writes_no_key(monkeypatch, tmp_path):
    apply_kid_setup, _, _ = _load_setup(monkeypatch, tmp_path)

    pdir = apply_kid_setup("kid", "local")

    cfg = yaml.safe_load((pdir / "config.yaml").read_text())
    assert cfg["model"]["provider"] == "custom"
    assert "11434" in cfg["model"]["base_url"]
    assert not (pdir / ".env").exists()  # local needs no secret


def test_rerun_is_idempotent_and_repairs_template(monkeypatch, tmp_path):
    apply_kid_setup, _, _ = _load_setup(monkeypatch, tmp_path)

    pdir = apply_kid_setup("kid", "local")
    # Simulate tampering: swap the builder toolset for a different one.
    cfg = yaml.safe_load((pdir / "config.yaml").read_text())
    cfg["platform_toolsets"]["cli"] = ["safe"]
    (pdir / "config.yaml").write_text(yaml.safe_dump(cfg))

    # Re-running re-applies the builder template.
    apply_kid_setup("kid", "local")
    repaired = yaml.safe_load((pdir / "config.yaml").read_text())
    assert repaired["platform_toolsets"]["cli"] == ["hermes-cli"]


def test_desktop_profile_name_matches_requested_profile(monkeypatch, tmp_path):
    """A non-default profile name must propagate to the desktop file too."""
    apply_kid_setup, _, kid_setup = _load_setup(monkeypatch, tmp_path)

    apply_kid_setup("junior", "local")

    desk = kid_setup.desktop_active_profile_path()
    assert json.loads(desk.read_text())["profile"] == "junior"


def test_inherit_copies_parent_model_and_keys(monkeypatch, tmp_path):
    apply_kid_setup, profiles, _ = _load_setup(monkeypatch, tmp_path)

    # Seed a parent (default profile) with a model + key.
    default_home = profiles.get_profile_dir("default")
    default_home.mkdir(parents=True, exist_ok=True)
    (default_home / "config.yaml").write_text(yaml.safe_dump({
        "model": {"provider": "openrouter", "default": "anthropic/claude-opus-4.6",
                  "base_url": "https://openrouter.ai/api/v1"}
    }))
    (default_home / ".env").write_text("OPENROUTER_API_KEY=sk-parent\nUNRELATED=x\n")

    pdir = apply_kid_setup("kid", "inherit", parent="default")

    cfg = yaml.safe_load((pdir / "config.yaml").read_text())
    assert cfg["model"]["provider"] == "openrouter"
    assert cfg["platform_toolsets"]["cli"] == ["hermes-cli"]  # builder toolset
    env = (pdir / ".env").read_text()
    assert "OPENROUTER_API_KEY=sk-parent" in env
    assert "UNRELATED" not in env  # only *_API_KEY entries inherited
