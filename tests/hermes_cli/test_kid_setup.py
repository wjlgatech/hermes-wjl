"""U6 — hermes kid-setup orchestrator.

Exercises apply_kid_setup against an isolated HERMES_HOME: it must seed the
locked-down profile, set the model, write the key, copy SOUL.md, and mark the
profile active. Re-running must be idempotent and repair the lockdown.
"""

import yaml


def _load_setup(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from hermes_cli import profiles
    from hermes_cli.subcommands.kid_setup import apply_kid_setup
    return apply_kid_setup, profiles


def test_free_mode_seeds_locked_profile_with_model_and_key(monkeypatch, tmp_path):
    apply_kid_setup, profiles = _load_setup(monkeypatch, tmp_path)

    pdir = apply_kid_setup("kid", "free", provider="nvidia", key="nvapi-secret")

    cfg = yaml.safe_load((pdir / "config.yaml").read_text())
    # Lockdown survived the template -> profile write.
    assert cfg["platform_toolsets"]["cli"] == ["safe"]
    assert cfg["display"]["personality"] == "kid"
    assert "kid" in cfg["agent"]["personalities"]
    # Model configured from the free provider.
    assert cfg["model"]["provider"] == "nvidia"
    assert cfg["model"]["base_url"].startswith("https://integrate.api.nvidia.com")
    # Persona + key landed.
    assert (pdir / "SOUL.md").exists() and (pdir / "SOUL.md").read_text().strip()
    assert "NVIDIA_API_KEY=nvapi-secret" in (pdir / ".env").read_text()
    # Active profile points at the kid (sticky active_profile file).
    assert profiles.get_active_profile() == "kid"


def test_local_mode_uses_ollama_and_writes_no_key(monkeypatch, tmp_path):
    apply_kid_setup, _ = _load_setup(monkeypatch, tmp_path)

    pdir = apply_kid_setup("kid", "local")

    cfg = yaml.safe_load((pdir / "config.yaml").read_text())
    assert cfg["model"]["provider"] == "custom"
    assert "11434" in cfg["model"]["base_url"]
    assert not (pdir / ".env").exists()  # local needs no secret


def test_rerun_is_idempotent_and_repairs_lockdown(monkeypatch, tmp_path):
    apply_kid_setup, _ = _load_setup(monkeypatch, tmp_path)

    pdir = apply_kid_setup("kid", "local")
    # Simulate tampering: widen the toolset.
    cfg = yaml.safe_load((pdir / "config.yaml").read_text())
    cfg["platform_toolsets"]["cli"] = ["coding"]
    (pdir / "config.yaml").write_text(yaml.safe_dump(cfg))

    # Re-running re-applies the locked template.
    apply_kid_setup("kid", "local")
    repaired = yaml.safe_load((pdir / "config.yaml").read_text())
    assert repaired["platform_toolsets"]["cli"] == ["safe"]


def test_inherit_copies_parent_model_and_keys(monkeypatch, tmp_path):
    apply_kid_setup, profiles = _load_setup(monkeypatch, tmp_path)

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
    assert cfg["platform_toolsets"]["cli"] == ["safe"]  # still locked down
    env = (pdir / ".env").read_text()
    assert "OPENROUTER_API_KEY=sk-parent" in env
    assert "UNRELATED" not in env  # only *_API_KEY entries inherited
