#!/usr/bin/env bash
# Merge one of YOUR feature branches into `main` — but ALWAYS sync the latest
# official Hermes into main FIRST, so main never falls behind upstream.
#
#   bash scripts/wjl-merge-feature.sh <feature-branch>
#   bash scripts/wjl-merge-feature.sh feat/cockpit
#
# This is the "always sync upstream before I merge a feature" workflow.
set -euo pipefail

FEATURE="${1:?usage: bash scripts/wjl-merge-feature.sh <feature-branch>}"
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

# 1) Always pull the latest official Hermes into main first.
bash "$ROOT/scripts/wjl-sync-upstream.sh"

# 2) Then merge your feature on top and push.
echo "→ merging '$FEATURE' into main…"
if git merge --no-edit "$FEATURE"; then
  git push origin main
  echo "✓ Synced upstream + merged '$FEATURE' into main."
else
  echo "✗ Conflict merging '$FEATURE'. Resolve, then:" >&2
  echo "    git add -A && git commit && git push origin main" >&2
  exit 1
fi
