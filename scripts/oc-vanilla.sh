#!/usr/bin/env bash
# Vanilla mode: full upstream Superpowers, OpenCode build agent.
set -euo pipefail
MODE="$HOME/.config/opencode/modes/vanilla"
CONFIG="$MODE/opencode.jsonc"
[[ -f "$CONFIG" ]] || { echo "Vanilla mode is not deployed at $MODE. Run scripts/setup-unix.sh first." >&2; exit 1; }
export OPENCODE_CONFIG="$CONFIG"
unset OPENCODE_CONFIG_DIR OPENCODE_CONFIG_CONTENT 2>/dev/null || true
unset OPENCODE_DISABLE_EXTERNAL_SKILLS 2>/dev/null || true
# A parent shell may have exported the Core-incompatible switch; clear it so the
# default provider plugins stay enabled for the pinned model.
unset OPENCODE_DISABLE_DEFAULT_PLUGINS
# Vanilla inherits the global config directory; only Core uses an isolated config root.
exec opencode "$@"
