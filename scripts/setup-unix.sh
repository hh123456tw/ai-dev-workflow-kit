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

CORE_SKILLS=(test-driven-development systematic-debugging verification-before-completion requesting-code-review receiving-code-review finishing-a-development-branch)
REQUIRED_SUPERPOWERS_VERSION="6.3.0"

read_superpowers_version() {
  python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['version'])" "$1" 2>/dev/null \
    || node -e "console.log(require(process.argv[1]).version)" "$1" 2>/dev/null \
    || true
}

# Parse a bare major.minor.patch version into a zero-padded key so two versions
# can be compared with a plain string comparison. Prints nothing unless the whole
# string is a bare triple, so version selection never needs a GNU-only `sort -V`.
superpowers_version_key() {
  local version="$1"
  if [[ "$version" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
    printf '%010d.%010d.%010d\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}"
  fi
}

# The cache nests by source path, for example
# packages/superpowers@git+https_/github.com/obra/superpowers.git/node_modules/superpowers
# so a single-level glob misses it. Match the package.json path itself with a
# portable `find` form (no GNU-only `-maxdepth`), then take its directory. Only
# directories that also carry a skills/ directory are considered.
find_superpowers_package() {
  local candidate candidate_version candidate_key
  local best="" best_key="" first=""
  while IFS= read -r candidate; do
    [[ -n "$candidate" ]] || continue
    [[ -f "$candidate/package.json" && -d "$candidate/skills" ]] || continue
    [[ -n "$first" ]] || first="$candidate"
    candidate_version="$(read_superpowers_version "$candidate/package.json")"
    if [[ "$candidate_version" == "$REQUIRED_SUPERPOWERS_VERSION" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
    candidate_key="$(superpowers_version_key "$candidate_version")"
    # Prefer a candidate with a readable, parseable version over one without;
    # among parseable versions keep the highest. String comparison is safe
    # because the key is zero-padded to a fixed width.
    if [[ -n "$candidate_key" ]]; then
      if [[ -z "$best_key" || "$candidate_key" > "$best_key" ]]; then
        best="$candidate"
        best_key="$candidate_key"
      fi
    fi
  done < <(find "$HOME/.cache/opencode/packages" -type f -name package.json -path '*/superpowers/package.json' 2>/dev/null | while IFS= read -r p; do dirname "$p"; done | sort)
  # No pinned match: return the newest parseable candidate, or the first one
  # found when none parses, so the version check can report the real string.
  if [[ -n "$best" ]]; then
    printf '%s\n' "$best"
  else
    printf '%s\n' "$first"
  fi
}

OC_CONFIG="$HOME/.config/opencode"
MODES_DIR="$OC_CONFIG/modes"

printf '[0/6] Backing up managed configuration...\n'
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$OC_CONFIG/backup_$STAMP"
mkdir -p "$BACKUP"
for item in opencode.jsonc agents commands modes; do
  # Copy only when the source exists; a genuine copy failure must surface rather
  # than being swallowed by an `|| true` arm.
  if [[ -e "$OC_CONFIG/$item" ]]; then
    cp -R "$OC_CONFIG/$item" "$BACKUP/"
  fi
done
i=0
for d in $(ls -d "$OC_CONFIG"/backup_* 2>/dev/null | sort -r); do
  i=$((i + 1))
  [[ $i -gt 3 ]] && rm -rf "$d"
done
echo "  backup written to $BACKUP"

printf '[1/6] Installing/updating gstack...\n'
GSTACK="$HOME/.local/share/gstack"
mkdir -p "$(dirname "$GSTACK")"
if [[ -d "$GSTACK/.git" ]]; then git -C "$GSTACK" pull --ff-only; else git clone https://github.com/garrytan/gstack.git "$GSTACK"; fi
bash "$GSTACK/setup" --host opencode

printf '[2/6] Deploying shared global agents and commands...\n'
mkdir -p "$OC_CONFIG/agents" "$OC_CONFIG/commands"
cp "$ROOT"/agents/*.md "$OC_CONFIG/agents/"
cp "$ROOT"/commands/*.md "$OC_CONFIG/commands/"
for agent in stable-lead.md explorer.md implementer.md reviewer.md test-writer.md; do
  [[ -f "$OC_CONFIG/agents/$agent" ]] || { echo "Agent was not deployed: $agent" >&2; exit 1; }
done
[[ -f "$OC_CONFIG/commands/stable.md" ]] || { echo 'Command was not deployed: stable.md' >&2; exit 1; }
echo '  deployed stable-lead, DeepSeek workers, /stable, /gstack-* commands.'

printf '[3/6] Deploying the three isolated mode directories...\n'
mkdir -p "$MODES_DIR"
for mode in vanilla stable; do
  mkdir -p "$MODES_DIR/$mode"
  cp "$ROOT/modes/$mode/opencode.jsonc" "$MODES_DIR/$mode/opencode.jsonc"
done
CORE_DIR="$MODES_DIR/core"
mkdir -p "$CORE_DIR/agents" "$CORE_DIR/xdg"
cp "$ROOT/modes/core/opencode.jsonc" "$CORE_DIR/opencode.jsonc"
cp "$ROOT/modes/core/agents/core-lead.md" "$CORE_DIR/agents/"
for worker in explorer.md implementer.md reviewer.md test-writer.md; do
  cp "$ROOT/agents/$worker" "$CORE_DIR/agents/"
done
for script in oc-vanilla.sh oc-stable.sh oc-core.sh; do
  cp "$ROOT/scripts/$script" "$MODES_DIR/$script"
done
echo "  deployed vanilla, stable, core, and mode launchers under $MODES_DIR."

# The stock OpenCode shortcut and the stock global config are Stable. Install the
# portable global config only when none exists; never overwrite the user's own.
GLOBAL_CONFIG="$OC_CONFIG/opencode.jsonc"
if [[ ! -e "$GLOBAL_CONFIG" ]]; then
  cp "$ROOT/global/opencode.jsonc" "$GLOBAL_CONFIG"
  echo '  installed global opencode.jsonc (was missing), so the stock shortcut runs Stable.'
else
  echo '  global opencode.jsonc exists; left untouched.'
  grep -q 'superpowers' "$GLOBAL_CONFIG" || echo '  warning: it does not load the Superpowers plugin.' >&2
  grep -q '"default_agent"' "$GLOBAL_CONFIG" || echo '  warning: it sets no default_agent.' >&2
fi

printf '[4/6] Deploying Core skills from the installed Superpowers package...\n'
SUPERPOWERS="$(find_superpowers_package)"
[[ -n "$SUPERPOWERS" ]] || { echo 'Superpowers package not found under ~/.cache/opencode/packages. Launch OpenCode once in Stable so the plugin installs, then re-run setup.' >&2; exit 1; }
VERSION="$(read_superpowers_version "$SUPERPOWERS/package.json")"
[[ "$VERSION" == "$REQUIRED_SUPERPOWERS_VERSION" ]] || { echo "Superpowers $VERSION found but $REQUIRED_SUPERPOWERS_VERSION is required. Update the repository pin deliberately." >&2; exit 1; }
rm -rf "$CORE_DIR/skills"
mkdir -p "$CORE_DIR/skills"
for skill in "${CORE_SKILLS[@]}"; do
  [[ -d "$SUPERPOWERS/skills/$skill" ]] || { echo "Core skill missing from Superpowers package: $skill" >&2; exit 1; }
  cp -R "$SUPERPOWERS/skills/$skill" "$CORE_DIR/skills/$skill"
done
{
  printf '{\n  "superpowers_version": "%s",\n  "skills": [' "$VERSION"
  printf '"%s"' "${CORE_SKILLS[0]}"
  for skill in "${CORE_SKILLS[@]:1}"; do printf ', "%s"' "$skill"; done
  printf '],\n  "deployed_at": "%s"\n}\n' "$(date -Iseconds)"
} > "$CORE_DIR/skills/manifest.json"
echo "  deployed ${#CORE_SKILLS[@]} Core skills from Superpowers $VERSION."

printf '[5/6] Installing CLI launchers...\n'
mkdir -p "$HOME/.local/bin"
for mode in vanilla stable core; do
  chmod +x "$MODES_DIR/oc-$mode.sh"
  ln -sf "$MODES_DIR/oc-$mode.sh" "$HOME/.local/bin/oc-$mode"
done
echo '  installed oc-vanilla, oc-stable, oc-core. Ensure ~/.local/bin is on PATH.'

printf '[6/6] Cleaning up retired artifacts...\n'
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
  "$OC_CONFIG/profiles"
  "$HOME/.local/bin/oc-product"
)
PRESENT=()
for item in "${LEGACY[@]}"; do [[ -e "$item" ]] && PRESENT+=("$item") || true; done
if [[ ${#PRESENT[@]} -eq 0 ]]; then
  echo '  no retired artifacts found.'
elif [[ $CLEAN_LEGACY -eq 1 ]]; then
  for item in "${PRESENT[@]}"; do rm -rf "$item"; echo "  removed retired artifact: $item"; done
else
  echo 'warning: retired artifacts still present. Re-run with --clean-legacy to remove them:' >&2
  for item in "${PRESENT[@]}"; do echo "    $item"; done
fi

echo ''
echo 'Restore complete.'
echo 'Modes: oc-vanilla (upstream Superpowers), oc-stable (cost-control lead), oc-core (autonomous Hackathon).'
echo 'Desktop shortcuts are Windows-only; Unix exposes the three CLI launchers.'
