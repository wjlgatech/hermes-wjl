#!/usr/bin/env bash
# Pull the latest official Hermes (NousResearch/hermes-agent:main) into this
# fork's `main`. Safe to run anytime; the hourly GitHub Action does the same.
#
#   bash scripts/wjl-sync-upstream.sh
#
# Run it from a clone of wjlgatech/hermes-wjl where `origin` = your fork.
set -euo pipefail

UPSTREAM_URL="https://github.com/NousResearch/hermes-agent.git"

cd "$(git rev-parse --show-toplevel)"
git fetch origin main --quiet
git checkout main
git pull --ff-only origin main

echo "→ fetching official Hermes…"
git fetch "$UPSTREAM_URL" main --quiet

if git merge --no-edit FETCH_HEAD; then
  git push origin main
  echo "✓ main is now in sync with official Hermes (NousResearch:main)."
else
  echo "✗ Merge conflict with upstream. Resolve it, then:" >&2
  echo "    git add -A && git commit && git push origin main" >&2
  exit 1
fi
