"""U5 — /free-llm-kid LLM config builder.

Tests the pure ``build_kid_model_config`` logic for each mode (free / local /
inherit) and its error paths. No network or filesystem.
"""

import pytest

from hermes_cli.kid_llm import (
    FREE_PROVIDERS,
    LOCAL_OLLAMA,
    build_kid_model_config,
    free_provider_signup,
)


def test_free_mode_writes_provider_base_url_and_key():
    cfg, env = build_kid_model_config("free", provider="nvidia", free_key="nvapi-xxx")
    assert cfg["provider"] == "nvidia"
    assert cfg["base_url"] == FREE_PROVIDERS["nvidia"]["base_url"]
    assert cfg["default"]  # a model id is set
    assert env == {"NVIDIA_API_KEY": "nvapi-xxx"}


def test_free_mode_without_key_writes_no_env():
    # e.g. NVIDIA_API_KEY already in the environment; config still valid.
    cfg, env = build_kid_model_config("free", provider="groq")
    assert cfg["provider"] == "groq"
    assert env == {}


def test_free_mode_custom_model_override():
    cfg, _ = build_kid_model_config("free", provider="nvidia", model="meta/llama-3.1-8b-instruct")
    assert cfg["default"] == "meta/llama-3.1-8b-instruct"


def test_free_mode_unknown_provider_raises():
    with pytest.raises(ValueError):
        build_kid_model_config("free", provider="not-a-provider")


def test_local_mode_uses_ollama_and_no_key():
    cfg, env = build_kid_model_config("local")
    assert cfg["provider"] == "custom"
    assert cfg["base_url"] == LOCAL_OLLAMA["base_url"]
    assert env == {}  # local needs no secret


def test_local_mode_custom_url_and_model():
    cfg, _ = build_kid_model_config(
        "local", ollama_url="http://127.0.0.1:1234/v1", ollama_model="qwen2.5"
    )
    assert cfg["base_url"] == "http://127.0.0.1:1234/v1"
    assert cfg["default"] == "qwen2.5"


def test_inherit_copies_parent_model_and_key():
    parent = {"provider": "openrouter", "default": "anthropic/claude-opus-4.6",
              "base_url": "https://openrouter.ai/api/v1"}
    cfg, env = build_kid_model_config(
        "inherit", parent_model=parent, parent_key_env="OPENROUTER_API_KEY", parent_key="sk-abc"
    )
    assert cfg == parent
    assert cfg is not parent  # copied, not aliased — kid edits don't touch parent
    assert env == {"OPENROUTER_API_KEY": "sk-abc"}


def test_inherit_without_parent_model_raises():
    with pytest.raises(ValueError):
        build_kid_model_config("inherit")


def test_unknown_mode_raises():
    with pytest.raises(ValueError):
        build_kid_model_config("magic")


def test_signup_url_available_for_each_free_provider():
    for provider in FREE_PROVIDERS:
        assert free_provider_signup(provider).startswith("http")
