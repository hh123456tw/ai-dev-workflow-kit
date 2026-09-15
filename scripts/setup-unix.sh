#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_LAUNCHERS=0
[[ "${1:-}" == "--install-launchers" ]] && INSTALL_LAUNCHERS=1
command -v git >/dev/null || { echo 'git required' >&2; exit 1; }
command -v opencode >/dev/null || { echo 'opencode required' >&2; exit 1; }

printf '[1/4] Preparing TEAM Matt skills...\n'
TEAM="$ROOT/profiles/team/skills"
mkdir -p "$TEAM"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git clone --depth 1 https://github.com/mattpocock/skills.git "$TMP/matt"
wanted=(setup-matt-pocock-skills grill-with-docs grill-me wayfinder to-spec to-tickets tdd codebase-design domain-modeling diagnosing-bugs code-review research handoff)
for name in "${wanted[@]}"; do
  src="$(find "$TMP/matt/skills" -type f -name SKILL.md -path "*/$name/SKILL.md" -print -quit | xargs -r dirname)"
  if [[ -z "$src" ]]; then echo "warning: Matt skill not found upstream: $name" >&2; continue; fi
  rm -rf "$TEAM/$name"
  cp -R "$src" "$TEAM/$name"
  echo "  installed Matt skill: $name"
done

printf '[2/4] Installing/updating gstack with gstack- prefix...\n'
GSTACK="$HOME/.local/share/gstack"
mkdir -p "$(dirname "$GSTACK")"
if [[ -d "$GSTACK/.git" ]]; then git -C "$GSTACK" pull --ff-only; else git clone https://github.com/garrytan/gstack.git "$GSTACK"; fi
bash "$GSTACK/setup" --host opencode --prefix

printf '[3/4] Checking local model file...\n'
mkdir -p "$ROOT/.local"
if [[ ! -f "$ROOT/.local/models.sh" ]]; then
  cp "$ROOT/scripts/models.sh.example" "$ROOT/.local/models.sh"
  echo "warning: edit $ROOT/.local/models.sh with actual IDs from OpenCode /models" >&2
fi

printf '[4/4] Launchers...\n'
if [[ $INSTALL_LAUNCHERS -eq 1 ]]; then
  mkdir -p "$HOME/.local/bin"
  ln -sf "$ROOT/scripts/oc-product.sh" "$HOME/.local/bin/oc-product"
  ln -sf "$ROOT/scripts/oc-team.sh" "$HOME/.local/bin/oc-team"
  echo 'Ensure ~/.local/bin is on PATH.'
fi

echo 'Restore complete. PRODUCT Superpowers installs from its plugin declaration on first launch.'
