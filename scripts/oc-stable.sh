#!/usr/bin/env bash
# Stable mode: full Superpowers plus the cost-control lead. Safe daily default.
set -euo pipefail
MODE="$HOME/.config/opencode/modes/stable"
CONFIG="$MODE/opencode.jsonc"
[[ -f "$CONFIG" ]] || { echo "Stable mode is not deployed at $MODE. Run scripts/setup-unix.sh first." >&2; exit 1; }
export OPENCODE_CONFIG="$CONFIG"
unset OPENCODE_CONFIG_DIR OPENCODE_CONFIG_CONTENT 2>/dev/null || true
unset OPENCODE_DISABLE_EXTERNAL_SKILLS 2>/dev/null || true
# A parent shell may have exported the Core-incompatible switch; clear it so the
# default provider plugins stay enabled for the pinned model.
unset OPENCODE_DISABLE_DEFAULT_PLUGINS
# Stable inherits the global config directory; only Core uses an isolated config root.
exec opencode "$@"
