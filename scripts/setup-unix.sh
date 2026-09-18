#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_LAUNCHERS=0
CLEAN_LEGACY=0
for arg in "$@"; do
  case "$arg" in
    --install-launchers) INSTALL_LAUNCHERS=1 ;;
    --clean-legacy) CLEAN_LEGACY=1 ;;
    *) echo "unknown option: $arg" >&2; exit 1 ;;
  esac
done
command -v git >/dev/null || { echo 'git required' >&2; exit 1; }
command -v opencode >/dev/null || { echo 'opencode required' >&2; exit 1; }

printf '[0/5] Pruning old backups (keep newest 3)...\n'
BACKUP_ROOT="$HOME/.config/opencode"
if [[ -d "$BACKUP_ROOT" ]]; then
  i=0
  for d in $(ls -d "$BACKUP_ROOT"/backup_* 2>/dev/null | sort -r); do
    i=$((i + 1))
    if [[ $i -gt 3 ]]; then rm -rf "$d"; echo "  pruned old backup: $d"; fi
  done
fi

printf '[1/5] Installing/updating gstack...\n'
GSTACK="$HOME/.local/share/gstack"
mkdir -p "$(dirname "$GSTACK")"
if [[ -d "$GSTACK/.git" ]]; then git -C "$GSTACK" pull --ff-only; else git clone https://github.com/garrytan/gstack.git "$GSTACK"; fi
# NOTE: gstack installs skills flat (no namespace). The selected toolbox is qa,
# qa-only, review, ship, cso, investigate, plan-ceo-review, design-review,
# benchmark. Namespaced entry points (/gstack-qa etc.) are deployed from this
# repo's commands/ in step [3/5]. `retro` is intentionally excluded: gstack
# defines it and this repo does not wrap it.
bash "$GSTACK/setup" --host opencode

printf '[2/5] Checking local model file...\n'
mkdir -p "$ROOT/.local"
CREATED_MODELS=0
if [[ ! -f "$ROOT/.local/models.sh" ]]; then
  cp "$ROOT/scripts/models.sh.example" "$ROOT/.local/models.sh"
  CREATED_MODELS=1
  echo "warning: edit $ROOT/.local/models.sh with actual IDs from OpenCode /models" >&2
fi
if [[ $CREATED_MODELS -eq 1 ]]; then
  echo "edit $ROOT/.local/models.sh with actual OpenCode model IDs, then run setup again" >&2
  exit 1
fi

printf '[3/5] Deploying shared agents and commands...\n'
OC_CONFIG="$HOME/.config/opencode"
mkdir -p "$OC_CONFIG/agents" "$OC_CONFIG/commands"
cp "$ROOT"/agents/*.md "$OC_CONFIG/agents/"
cp "$ROOT"/commands/*.md "$OC_CONFIG/commands/"
for agent in stable-lead.md explorer.md implementer.md reviewer.md test-writer.md; do
  [[ -f "$OC_CONFIG/agents/$agent" ]] || { echo "Agent was not deployed: $agent" >&2; exit 1; }
done
[[ -f "$OC_CONFIG/commands/stable.md" ]] || { echo 'Command was not deployed: stable.md' >&2; exit 1; }
echo '  deployed stable-lead, DeepSeek workers (explorer/implementer/reviewer/test-writer), /stable, /gstack-* commands.'
echo '  The profile resolves stable-lead from this global agents directory; run setup before launching oc-product.'

printf '[4/5] Deploying portable global config and gstack routing...\n'
GLOBAL_CONFIG="$OC_CONFIG/opencode.jsonc"
if [[ ! -f "$GLOBAL_CONFIG" ]]; then
  cp "$ROOT/global/opencode.jsonc" "$GLOBAL_CONFIG"
  echo '  installed global opencode.jsonc (was missing).'
else
  echo "warning: global opencode.jsonc exists; left untouched (file: $GLOBAL_CONFIG)." >&2
  if grep -q 'opencode-ensemble' "$GLOBAL_CONFIG"; then
    echo 'warning: it still references @hueyexe/opencode-ensemble. The multi-agent layer is retired; remove that plugin entry by hand.' >&2
  fi
fi
if [[ ! -f "$OC_CONFIG/gstack.jsonc" ]]; then
  cp "$ROOT/gstack/gstack.jsonc" "$OC_CONFIG/gstack.jsonc"
  echo '  installed gstack.jsonc (was missing).'
else
  echo '  gstack.jsonc exists; left untouched (diff against repo gstack/ if drifted).'
fi

printf '[5/5] Launchers and legacy cleanup...\n'
if [[ $INSTALL_LAUNCHERS -eq 1 ]]; then
  mkdir -p "$HOME/.local/bin"
  ln -sf "$ROOT/scripts/oc-product.sh" "$HOME/.local/bin/oc-product"
  echo 'Ensure ~/.local/bin is on PATH.'
fi

LEGACY=(
  "$OC_CONFIG/agents/team-lead.md"
  "$OC_CONFIG/agents/team-scout.md"
  "$OC_CONFIG/agents/team-builder.md"
  "$OC_CONFIG/agents/team-reviewer.md"
  "$OC_CONFIG/commands/team.md"
  "$OC_CONFIG/ensemble.json"
  "$OC_CONFIG/profiles/team.json"
  "$OC_CONFIG/profiles/team"
)
PRESENT=()
for item in "${LEGACY[@]}"; do [[ -e "$item" ]] && PRESENT+=("$item"); done
if [[ ${#PRESENT[@]} -eq 0 ]]; then
  echo '  no retired multi-agent artifacts found.'
elif [[ $CLEAN_LEGACY -eq 1 ]]; then
  for item in "${PRESENT[@]}"; do rm -rf "$item"; echo "  removed retired artifact: $item"; done
else
  echo 'warning: retired multi-agent artifacts still present. Re-run with --clean-legacy to remove them:' >&2
  for item in "${PRESENT[@]}"; do echo "    $item"; done
fi

echo 'Restore complete. Superpowers installs from the profile plugin declaration on first launch.'
