#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODELS="$ROOT/.local/models.sh"
[[ -f "$MODELS" ]] || { echo "Missing $MODELS; copy scripts/models.sh.example and fill actual model IDs." >&2; exit 1; }
# shellcheck source=/dev/null
source "$MODELS"
: "${OPENCODE_PRIMARY_MODEL:?OPENCODE_PRIMARY_MODEL is empty}"
: "${OPENCODE_WORKER_MODEL:?OPENCODE_WORKER_MODEL is empty}"
OPENCODE_CONFIG="$ROOT/profiles/team/opencode.jsonc" \
OPENCODE_CONFIG_DIR="$ROOT/profiles/team" \
opencode "$@"
