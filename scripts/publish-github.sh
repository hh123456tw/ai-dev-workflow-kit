#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="${1:-opencode-dev-profiles}"
VISIBILITY="${2:-private}"
[[ "$VISIBILITY" == private || "$VISIBILITY" == public ]] || { echo 'visibility must be private or public' >&2; exit 2; }
command -v gh >/dev/null || { echo 'GitHub CLI (gh) required. Install it and run: gh auth login' >&2; exit 1; }
cd "$ROOT"
gh auth status
if git remote get-url origin >/dev/null 2>&1; then
  git push -u origin HEAD
else
  gh repo create "$NAME" "--$VISIBILITY" --source . --remote origin --push
fi
