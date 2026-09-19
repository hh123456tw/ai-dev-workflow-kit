#!/usr/bin/env bash
# Core mode: autonomous Hackathon/MVP lead with a curated skill set.
# Isolation: own config dir, own XDG config root, no external skills, no default plugins.
set -euo pipefail
MODE="$HOME/.config/opencode/modes/core"
CONFIG="$MODE/opencode.jsonc"
[[ -f "$CONFIG" ]] || { echo "Core mode is not deployed at $MODE. Run scripts/setup-unix.sh first." >&2; exit 1; }
[[ -d "$MODE/skills/test-driven-development" ]] || { echo "Core skills are missing at $MODE/skills. Re-run scripts/setup-unix.sh." >&2; exit 1; }
export OPENCODE_CONFIG="$CONFIG"
export OPENCODE_CONFIG_DIR="$MODE"
export XDG_CONFIG_HOME="$MODE/xdg"
export OPENCODE_DISABLE_EXTERNAL_SKILLS=1
export OPENCODE_DISABLE_DEFAULT_PLUGINS=1
unset OPENCODE_CONFIG_CONTENT 2>/dev/null || true
exec opencode --pure "$@"
