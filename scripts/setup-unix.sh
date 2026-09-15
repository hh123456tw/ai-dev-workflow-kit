#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_LAUNCHERS=0
[[ "${1:-}" == "--install-launchers" ]] && INSTALL_LAUNCHERS=1
command -v git >/dev/null || { echo 'git required' >&2; exit 1; }
command -v opencode >/dev/null || { echo 'opencode required' >&2; exit 1; }

printf '[1/7] Preparing TEAM Matt skills...\n'
TEAM="$ROOT/profiles/team/skills"
mkdir -p "$TEAM"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git clone --depth 1 https://github.com/mattpocock/skills.git "$TMP/matt"
wanted=(setup-matt-pocock-skills grill-with-docs grill-me wayfinder to-spec to-tickets implement tdd codebase-design domain-modeling diagnosing-bugs code-review research resolving-merge-conflicts handoff)
for name in "${wanted[@]}"; do
  src="$(find "$TMP/matt/skills" -type f -name SKILL.md -path "*/$name/SKILL.md" -print -quit | xargs -r dirname)"
  if [[ -z "$src" ]]; then echo "warning: Matt skill not found upstream: $name" >&2; continue; fi
  rm -rf "$TEAM/$name"
  cp -R "$src" "$TEAM/$name"
  echo "  installed Matt skill: $name"
done

printf '[2/7] Installing/updating gstack...\n'
GSTACK="$HOME/.local/share/gstack"
mkdir -p "$(dirname "$GSTACK")"
if [[ -d "$GSTACK/.git" ]]; then git -C "$GSTACK" pull --ff-only; else git clone https://github.com/garrytan/gstack.git "$GSTACK"; fi
# NOTE: gstack installs skills flat (no namespace). The selected toolbox used by
# STABLE/TEAM modes is qa, qa-only, review, ship, cso, investigate,
# plan-ceo-review, design-review, benchmark. Namespaced entry points
# (/gstack-qa etc.) are deployed from this repo's commands/ in step [5/6].
# `retro` is intentionally excluded: Matt and gstack both define it.
bash "$GSTACK/setup" --host opencode

printf '[3/7] Checking local model file...\n'
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

printf '[4/7] Installing TEAM Ensemble configuration...\n'
mkdir -p "$HOME/.config/opencode"
sed "s|__OPENCODE_WORKER_MODEL__|${OPENCODE_WORKER_MODEL}|g" "$ROOT/profiles/team/ensemble.json.template" > "$HOME/.config/opencode/ensemble.json"

printf '[5/7] Deploying shared agents and commands...\n'
mkdir -p "$HOME/.config/opencode/agents" "$HOME/.config/opencode/commands"
cp "$ROOT"/agents/*.md "$HOME/.config/opencode/agents/"
cp "$ROOT"/commands/*.md "$HOME/.config/opencode/commands/"
echo '  deployed stable-lead, team-lead, DeepSeek workers, /stable, /team, /gstack-* commands.'
echo '  NOTE: repo reviewer.md (DeepSeek) deploys to global agents/; the TEAM profile keeps its own GPT reviewer.'

printf '[6/7] Deploying portable global config and gstack routing...\n'
if [[ ! -f "$HOME/.config/opencode/opencode.jsonc" ]]; then
  cp "$ROOT/global/opencode.jsonc" "$HOME/.config/opencode/opencode.jsonc"
  echo '  installed global opencode.jsonc (was missing).'
else
  echo '  global opencode.jsonc exists; left untouched (diff against repo global/ if drifted).'
fi
if [[ ! -f "$HOME/.config/opencode/gstack.jsonc" ]]; then
  cp "$ROOT/gstack/gstack.jsonc" "$HOME/.config/opencode/gstack.jsonc"
  echo '  installed gstack.jsonc (was missing).'
else
  echo '  gstack.jsonc exists; left untouched (diff against repo gstack/ if drifted).'
fi

printf '[7/7] Launchers...\n'
if [[ $INSTALL_LAUNCHERS -eq 1 ]]; then
  mkdir -p "$HOME/.local/bin"
  ln -sf "$ROOT/scripts/oc-product.sh" "$HOME/.local/bin/oc-product"
  ln -sf "$ROOT/scripts/oc-team.sh" "$HOME/.local/bin/oc-team"
  echo 'Ensure ~/.local/bin is on PATH.'
fi

echo 'Restore complete. PRODUCT Superpowers installs from its plugin declaration on first launch.'
