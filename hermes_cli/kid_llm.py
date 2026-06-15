"""Kid LLM configuration — shared logic for the `/free-llm-kid` skill (U5) and
the `hermes kid-setup` command (U6).

Builds the ``model`` config block + ``.env`` entries for a child's profile from
one of three modes:

* ``free``    — a free-tier cloud provider (NVIDIA NIM / Groq / Gemini). Free to
                the parent, good quality, needs a free key signup.
* ``local``   — a local model via Ollama (OpenAI-compatible ``custom`` endpoint).
                Private, offline, no key — the fallback when free-tier is
                unavailable/rate-limited.
* ``inherit`` — copy the parent's model + key into the kid profile (opt-in;
                carries the parent's cost/abuse risk).

The default survival chain is free-tier → local (see :data:`DEFAULT_CHAIN`).

This module is pure config construction — no network, no filesystem. The caller
(kid-setup) writes the files and runs any live verification.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Tuple

# Free-tier providers a kid can use at no cost to the parent. Model defaults are
# reasonable starting points and may be overridden; they are not pinned forever.
FREE_PROVIDERS: Dict[str, Dict[str, str]] = {
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "key_env": "NVIDIA_API_KEY",
        "default_model": "meta/llama-3.3-70b-instruct",
        "signup": "https://build.nvidia.com",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "default_model": "llama-3.3-70b-versatile",
        "signup": "https://console.groq.com/keys",
    },
    "gemini": {
        # Gemini is a first-class provider (direct), so no base_url override.
        "base_url": "",
        "key_env": "GEMINI_API_KEY",
        "default_model": "gemini-2.0-flash",
        "signup": "https://aistudio.google.com/apikey",
    },
}

# Local Ollama via its OpenAI-compatible endpoint (provider alias "custom").
LOCAL_OLLAMA: Dict[str, str] = {
    "provider": "custom",
    "base_url": "http://127.0.0.1:11434/v1",
    "default_model": "llama3.2",
}

# Default preference order: try a free cloud model first, fall back to local.
DEFAULT_CHAIN: List[str] = ["free", "local"]

VALID_MODES = ("free", "local", "inherit")


def build_kid_model_config(
    mode: str,
    *,
    provider: str = "nvidia",
    model: Optional[str] = None,
    free_key: Optional[str] = None,
    ollama_url: Optional[str] = None,
    ollama_model: Optional[str] = None,
    parent_model: Optional[Mapping[str, str]] = None,
    parent_key_env: Optional[str] = None,
    parent_key: Optional[str] = None,
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Return ``(model_config, env)`` for a kid profile.

    ``model_config`` is the ``model:`` block for the profile's config.yaml;
    ``env`` is the set of KEY=value pairs to write into the profile's ``.env``
    (empty when no secret is needed, e.g. local Ollama).
    """
    if mode == "free":
        if provider not in FREE_PROVIDERS:
            raise ValueError(
                f"unknown free provider {provider!r}; choose one of {sorted(FREE_PROVIDERS)}"
            )
        spec = FREE_PROVIDERS[provider]
        model_config: Dict[str, str] = {
            "provider": provider,
            "default": model or spec["default_model"],
        }
        if spec["base_url"]:
            model_config["base_url"] = spec["base_url"]
        env = {spec["key_env"]: free_key} if free_key else {}
        return model_config, env

    if mode == "local":
        return (
            {
                "provider": LOCAL_OLLAMA["provider"],
                "default": ollama_model or LOCAL_OLLAMA["default_model"],
                "base_url": ollama_url or LOCAL_OLLAMA["base_url"],
            },
            {},  # local models need no key
        )

    if mode == "inherit":
        if not parent_model:
            raise ValueError("inherit mode requires the parent's model config")
        model_config = dict(parent_model)
        env = {parent_key_env: parent_key} if parent_key_env and parent_key else {}
        return model_config, env

    raise ValueError(f"unknown mode {mode!r}; choose one of {VALID_MODES}")


def free_provider_signup(provider: str) -> str:
    """Where the parent gets a free key for ``provider`` (for skill/CLI prompts)."""
    if provider not in FREE_PROVIDERS:
        raise ValueError(f"unknown free provider {provider!r}")
    return FREE_PROVIDERS[provider]["signup"]
