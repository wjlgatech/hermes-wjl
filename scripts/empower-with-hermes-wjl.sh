#!/usr/bin/env bash
# Point an EXISTING Hermes Desktop install at the hermes-wjl fork and set up a
# locked-or-builder kid profile — without rebuilding the Electron app (so it
# sidesteps the upstream @assistant-ui dependency break that currently fails
# `hermes update` / `--force-build`).
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/wjlgatech/hermes-wjl/main/scripts/empower-with-hermes-wjl.sh | bash -s -- --key <FREE_NVIDIA_KEY>
#
# Flags:
#   --key <k>     Free NVIDIA NIM key for the kid (get one free at build.nvidia.com)
#   --llm <mode>  free | local | inherit   (default: free; inherit copies your default profile's creds)
#   --model <m>   Model id (default: google/gemma-4-31b-it)
#   --profile <p> Kid profile name (default: kid)
set -euo pipefail

FORK_HTTPS="https://github.com/wjlgatech/hermes-wjl.git"
HERMES_AGENT="${HOME}/.hermes/hermes-agent"
KEY=""; LLM="free"; MODEL="google/gemma-4-31b-it"; PROFILE="kid"

while [ $# -gt 0 ]; do
  case "$1" in
    --key) KEY="$2"; shift 2 ;;
    --llm) LLM="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    *) echo "unknown flag: $1"; exit 1 ;;
  esac
done

if [ ! -d "$HERMES_AGENT/.git" ]; then
  echo "✗ No Hermes install found at $HERMES_AGENT."
  echo "  Install the desktop app first (or use the fork's install.sh), then re-run."
  exit 1
fi

echo "→ Pointing $HERMES_AGENT at the fork ($FORK_HTTPS)…"
git -C "$HERMES_AGENT" remote set-url origin "$FORK_HTTPS"
git -C "$HERMES_AGENT" fetch origin --quiet
git -C "$HERMES_AGENT" checkout main --quiet 2>/dev/null || git -C "$HERMES_AGENT" checkout -b main origin/main --quiet
git -C "$HERMES_AGENT" reset --hard origin/main --quiet
echo "  now at $(git -C "$HERMES_AGENT" rev-parse --short HEAD)"

echo "→ Reinstalling the Python backend (no Electron rebuild)…"
if command -v uv >/dev/null 2>&1; then
  ( cd "$HERMES_AGENT" && uv pip install -e . --quiet )
else
  "$HERMES_AGENT/venv/bin/python" -m pip install -e "$HERMES_AGENT" --quiet
fi

echo "→ Setting up the '$PROFILE' profile (kid mode, LLM: $LLM)…"
KID_ARGS=(kid-setup --profile "$PROFILE" --llm "$LLM" --model "$MODEL")
[ "$LLM" = "free" ] && [ -n "$KEY" ] && KID_ARGS+=(--provider nvidia --key "$KEY")
"$HERMES_AGENT/venv/bin/python" -m hermes_cli.main "${KID_ARGS[@]}"

# Point the DESKTOP app (separate from the CLI's active_profile) at the kid profile.
DESK_DIR="${HOME}/Library/Application Support/Hermes"
mkdir -p "$DESK_DIR"
printf '{"profile":"%s"}' "$PROFILE" > "$DESK_DIR/active-profile.json"
echo "  desktop will launch profile: $PROFILE"

echo "→ Launching the existing desktop app on the fork (no rebuild)…"
"$HERMES_AGENT/venv/bin/hermes" desktop --skip-build >/dev/null 2>&1 &

echo ""
echo "✅ Done. Your Hermes desktop app is now powered by hermes-wjl, in '$PROFILE' mode."
echo "   Switch back to your own profile anytime: rm \"$DESK_DIR/active-profile.json\" and relaunch."
