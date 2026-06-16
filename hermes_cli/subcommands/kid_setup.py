"""U6 — ``hermes kid-setup``.

One command that makes a child's machine ready: it seeds a "kid" **builder**
profile from ``templates/kid-profile/`` (full builder toolset + a content-
boundary persona — the guardrail is content, not capability), configures a free
LLM via the ``/free-llm-kid`` logic (free-tier cloud, local Ollama fallback, or
inherit the parent's credential), and marks the profile active — for BOTH the
CLI (``~/.hermes/active_profile``) and the desktop GUI (its own
``active-profile.json``) — so Hermes launches straight into kid mode with no
onboarding wall.

Re-running re-applies the template (repairing any drift/tampering), so it's safe
and idempotent.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

import yaml

from hermes_cli import profiles
from hermes_cli.kid_llm import build_kid_model_config

# templates/kid-profile/ at the repo root (this file is hermes_cli/subcommands/).
KID_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates" / "kid-profile"

# The desktop (Electron) app records which profile to launch in its OWN file,
# separate from the CLI's ~/.hermes/active_profile. It lives under Electron's
# userData dir, named after the app's productName ("Hermes" — see
# apps/desktop/package.json). startHermes() reads it (readActiveDesktopProfile)
# and launches `hermes --profile <name> dashboard`. If kid-setup only set the
# CLI active_profile, the GUI would still open the default profile — so we write
# this file too, mirroring scripts/empower-with-hermes-wjl.sh.
DESKTOP_APP_NAME = "Hermes"


def desktop_userdata_dir() -> Path:
    """Electron ``app.getPath('userData')`` for the Hermes desktop app.

    Replicates Electron's per-platform appData location + productName subdir so
    the Python CLI can point the GUI at the kid profile without the app running.
    Honors ``HERMES_DESKTOP_USERDATA`` as an explicit override (tests, custom
    installs).
    """
    override = os.environ.get("HERMES_DESKTOP_USERDATA")
    if override:
        return Path(override)

    home = Path.home()
    if sys.platform == "darwin":
        base = home / "Library" / "Application Support"
    elif sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
    else:  # linux / other unix
        base = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    return base / DESKTOP_APP_NAME


def desktop_active_profile_path() -> Path:
    return desktop_userdata_dir() / "active-profile.json"


def write_desktop_active_profile(name: str) -> Path:
    """Point the desktop app at profile ``name`` (matches main.cjs's format)."""
    path = desktop_active_profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"profile": name}, indent=2) + "\n")
    return path


def _template_config() -> dict:
    return yaml.safe_load((KID_TEMPLATE_DIR / "config.yaml").read_text())


def _read_parent_llm(parent: str) -> Tuple[dict, Dict[str, str]]:
    """Read a parent profile's model config + its *_API_KEY env entries."""
    pdir = profiles.get_profile_dir(parent)
    cfg_path = pdir / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
    model = (cfg or {}).get("model") or {}

    env: Dict[str, str] = {}
    env_path = pdir / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key.endswith("_API_KEY"):
                env[key] = value.strip()
    return model, env


def _write_env(path: Path, updates: Dict[str, str]) -> None:
    """Merge ``updates`` into a .env file, preserving unrelated lines."""
    lines = []
    seen = set()
    if path.exists():
        for line in path.read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key in updates:
                    lines.append(f"{key}={updates[key]}")
                    seen.add(key)
                    continue
            lines.append(line)
    for key, value in updates.items():
        if key not in seen:
            lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + ("\n" if lines else ""))


def apply_kid_setup(
    profile: str,
    mode: str,
    *,
    provider: str = "nvidia",
    key: Optional[str] = None,
    model: Optional[str] = None,
    ollama_url: Optional[str] = None,
    ollama_model: Optional[str] = None,
    parent: str = "default",
) -> Path:
    """Seed/repair the kid profile, set its model, and mark it active.

    Returns the profile directory. The template is (re)applied every run, so
    this both creates and repairs the profile.
    """
    name = profiles.normalize_profile_name(profile)
    pdir = profiles.get_profile_dir(name)
    pdir.mkdir(parents=True, exist_ok=True)

    # Authoritative config from the template (repairs any drift/tampering).
    cfg = _template_config()

    if mode == "inherit":
        parent_model, parent_env = _read_parent_llm(parent)
        if not parent_model:
            raise ValueError(
                f"cannot inherit: parent profile {parent!r} has no model configured"
            )
        model_cfg, env = dict(parent_model), parent_env
    else:
        model_cfg, env = build_kid_model_config(
            mode,
            provider=provider,
            model=model,
            free_key=key,
            ollama_url=ollama_url,
            ollama_model=ollama_model,
        )

    cfg["model"] = model_cfg
    (pdir / "config.yaml").write_text(
        yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True)
    )
    shutil.copyfile(KID_TEMPLATE_DIR / "SOUL.md", pdir / "SOUL.md")
    if env:
        _write_env(pdir / ".env", env)

    # Mark active so the desktop opens straight into kid mode (no onboarding).
    # The CLI honors ~/.hermes/active_profile; the GUI reads its own file.
    profiles.set_active_profile(name)
    write_desktop_active_profile(name)
    return pdir


def cmd_kid_setup(args: argparse.Namespace) -> int:
    pdir = apply_kid_setup(
        args.profile,
        args.llm,
        provider=args.provider,
        key=args.key,
        model=args.model,
        ollama_url=args.ollama_url,
        ollama_model=args.ollama_model,
        parent=args.parent,
    )
    name = profiles.normalize_profile_name(args.profile)
    print(f"✅ Kid profile '{name}' ready at {pdir}")
    print("   Full builder toolset + content-boundary persona applied; model "
          f"configured ({args.llm}).")
    if args.llm == "free" and not args.key:
        from hermes_cli.kid_llm import free_provider_signup
        try:
            print(f"   Free key needed for '{args.provider}': "
                  f"set its *_API_KEY env, or get one at {free_provider_signup(args.provider)}")
        except ValueError:
            pass
    print("   Launch:  hermes desktop   (opens straight into kid mode)")
    return 0


def build_kid_setup_parser(subparsers, *, cmd_kid_setup: Callable) -> None:
    """Attach the ``kid-setup`` subcommand to ``subparsers``."""
    parser = subparsers.add_parser(
        "kid-setup",
        help="Set up a free-LLM kid builder profile and make it active",
        description=(
            "Create/repair a child's builder profile (full toolset + a content-"
            "boundary persona), configure a free LLM (free-tier cloud with local "
            "fallback, or inherit a parent's credential), and mark it active for "
            "both the CLI and the desktop GUI so Hermes opens straight into kid "
            "mode."
        ),
    )
    parser.add_argument("--profile", default="kid", help="Profile name (default: kid)")
    parser.add_argument(
        "--llm", choices=["free", "local", "inherit"], default="free",
        help="LLM mode (default: free-tier cloud)",
    )
    parser.add_argument(
        "--provider", default="nvidia",
        help="Free provider for --llm free: nvidia | groq | gemini (default: nvidia)",
    )
    parser.add_argument("--key", help="API key for the free provider (else set its *_API_KEY env)")
    parser.add_argument("--model", help="Override the model id")
    parser.add_argument("--ollama-url", dest="ollama_url", help="Local Ollama base URL for --llm local")
    parser.add_argument("--ollama-model", dest="ollama_model", help="Local model id for --llm local")
    parser.add_argument("--parent", default="default", help="Profile to inherit from for --llm inherit")
    parser.set_defaults(func=cmd_kid_setup)
