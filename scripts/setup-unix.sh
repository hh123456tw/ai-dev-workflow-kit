#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLEAN_LEGACY=0
for arg in "$@"; do
  case "$arg" in
    --clean-legacy) CLEAN_LEGACY=1 ;;
    *) echo "unknown option: $arg" >&2; exit 1 ;;
  esac
done
command -v git >/dev/null || { echo 'git required' >&2; exit 1; }
command -v opencode >/dev/null || { echo 'opencode required' >&2; exit 1; }

printf '[0/3] Pruning old backups (keep newest 3)...\n'
BACKUP_ROOT="$HOME/.config/opencode"
if [[ -d "$BACKUP_ROOT" ]]; then
  i=0
  for d in $(ls -d "$BACKUP_ROOT"/backup_* 2>/dev/null | sort -r); do
    i=$((i + 1))
    if [[ $i -gt 3 ]]; then rm -rf "$d"; echo "  pruned old backup: $d"; fi
  done
fi

printf '[1/3] Installing/updating gstack...\n'
GSTACK="$HOME/.local/share/gstack"
mkdir -p "$(dirname "$GSTACK")"
if [[ -d "$GSTACK/.git" ]]; then git -C "$GSTACK" pull --ff-only; else git clone https://github.com/garrytan/gstack.git "$GSTACK"; fi
# NOTE: gstack installs skills flat (no namespace). The selected toolbox is qa,
# qa-only, review, ship, cso, investigate, plan-ceo-review, design-review,
# benchmark. Namespaced entry points (/gstack-qa etc.) are deployed from this
# repo's commands/ in step [2/3]. `retro` is intentionally excluded: gstack
# defines it and this repo does not wrap it.
bash "$GSTACK/setup" --host opencode

printf '[2/3] Deploying shared agents and commands...\n'
OC_CONFIG="$HOME/.config/opencode"
mkdir -p "$OC_CONFIG/agents" "$OC_CONFIG/commands"
cp "$ROOT"/agents/*.md "$OC_CONFIG/agents/"
cp "$ROOT"/commands/*.md "$OC_CONFIG/commands/"
for agent in stable-lead.md explorer.md implementer.md reviewer.md test-writer.md; do
  [[ -f "$OC_CONFIG/agents/$agent" ]] || { echo "Agent was not deployed: $agent" >&2; exit 1; }
done
[[ -f "$OC_CONFIG/commands/stable.md" ]] || { echo 'Command was not deployed: stable.md' >&2; exit 1; }
echo '  deployed stable-lead, DeepSeek workers (explorer/implementer/reviewer/test-writer), /stable, /gstack-* commands.'

printf '[3/3] Deploying portable global config and cleaning up retired artifacts...\n'
GLOBAL_CONFIG="$OC_CONFIG/opencode.jsonc"
if [[ ! -f "$GLOBAL_CONFIG" ]]; then
  cp "$ROOT/global/opencode.jsonc" "$GLOBAL_CONFIG"
  echo '  installed global opencode.jsonc (was missing).'
else
  echo "warning: global opencode.jsonc exists; left untouched (file: $GLOBAL_CONFIG)." >&2
  if grep -q 'opencode-ensemble' "$GLOBAL_CONFIG"; then
    echo 'warning: it still references @hueyexe/opencode-ensemble. The multi-agent layer is retired; remove that plugin entry by hand.' >&2
  fi
  if ! grep -q '"default_agent"' "$GLOBAL_CONFIG"; then
    echo 'warning: it sets no default_agent. Add "default_agent": "stable-lead" to start sessions as the lead.' >&2
  fi
fi
if [[ ! -f "$OC_CONFIG/gstack.jsonc" ]]; then
  cp "$ROOT/gstack/gstack.jsonc" "$OC_CONFIG/gstack.jsonc"
  echo '  installed gstack.jsonc (was missing).'
else
  echo '  gstack.jsonc exists; left untouched (diff against repo gstack/ if drifted).'
fi

LEGACY=(
  "$OC_CONFIG/agents/team-lead.md"
  "$OC_CONFIG/agents/team-scout.md"
  "$OC_CONFIG/agents/team-builder.md"
  "$OC_CONFIG/agents/team-reviewer.md"
  "$OC_CONFIG/commands/team.md"
  "$OC_CONFIG/ensemble.json"
  "$OC_CONFIG/ensemble.db"
  "$OC_CONFIG/ensemble.db-shm"
  "$OC_CONFIG/ensemble.db-wal"
  "$OC_CONFIG/profiles/team.json"
  "$OC_CONFIG/profiles/team"
  "$OC_CONFIG/profiles/product.json"
  "$OC_CONFIG/profiles/product"
  "$OC_CONFIG/profiles"
)
PRESENT=()
for item in "${LEGACY[@]}"; do [[ -e "$item" ]] && PRESENT+=("$item"); done
if [[ ${#PRESENT[@]} -eq 0 ]]; then
  echo '  no retired artifacts found.'
elif [[ $CLEAN_LEGACY -eq 1 ]]; then
  for item in "${PRESENT[@]}"; do rm -rf "$item"; echo "  removed retired artifact: $item"; done
else
  echo 'warning: retired artifacts still present. Re-run with --clean-legacy to remove them:' >&2
  for item in "${PRESENT[@]}"; do echo "    $item"; done
fi

echo 'Restore complete. Superpowers installs from the global plugin declaration on first launch.'
