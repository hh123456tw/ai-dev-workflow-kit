#!/usr/bin/env bash
# Stable mode: full Superpowers plus the cost-control lead. Safe daily default.
set -euo pipefail
MODE="$HOME/.config/opencode/modes/stable"
CONFIG="$MODE/opencode.jsonc"
[[ -f "$CONFIG" ]] || { echo "Stable mode is not deployed at $MODE. Run scripts/setup-unix.sh first." >&2; exit 1; }
export OPENCODE_CONFIG="$CONFIG"
unset OPENCODE_CONFIG_DIR OPENCODE_CONFIG_CONTENT 2>/dev/null || true
exec opencode "$@"
