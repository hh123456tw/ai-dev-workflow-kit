# OpenCode Desktop / TUI rebuild

The tracked config files are portable. Provider authentication is not.

## How this repo is used

Open OpenCode normally (the stock shortcut). The global config sets
`"default_agent": "stable-lead"`, so the session starts as the lead, and the
global plugin entry loads Superpowers. `/stable <request>` also works at any time.

There is no profile to switch, no launcher wrapper, and no per-machine model file.
Model routing lives in `global/opencode.jsonc`.

## Layout

| Path | Purpose |
| --- | --- |
| `agents/stable-lead.md` | The single lead definition, deployed to the global agents directory. |
| `agents/explorer.md`, `agents/implementer.md`, `agents/reviewer.md`, `agents/test-writer.md` | Bounded DeepSeek workers, deployed globally. |
| `commands/stable.md`, `commands/gstack-*.md` | The `/stable` and namespaced gstack commands. |
| `global/opencode.jsonc` | Portable global config, installed only when none exists. |

## Rebuild

1. Install OpenCode.
2. Authenticate the same providers locally.
3. Run `scripts/setup-windows.ps1` or `scripts/setup-unix.sh`.
4. Open OpenCode.

## Remove stale deployed artifacts

Earlier generations deployed a multi-agent Team workflow, a Team profile, a
product profile, and an `oc-product` wrapper. All of that is retired. Delete these
from the deployed OpenCode config directory (for example
`%USERPROFILE%\.config\opencode\` on Windows or `~/.config/opencode/` on
macOS/Linux):

- `agents/team-lead.md`, `agents/team-scout.md`, `agents/team-builder.md`,
  `agents/team-reviewer.md`
- `commands/team.md`
- the whole `profiles/` directory (`team.json`, `team/`, `product.json`,
  `product/`)
- `ensemble.json`, `ensemble.db`, `ensemble.db-shm`, `ensemble.db-wal`
- any `@hueyexe/opencode-ensemble` entry still present in the global
  `opencode.jsonc`
- the `oc-product` wrapper, wherever it was installed (for example
  `%APPDATA%\npm\oc-product.cmd`)

Setup's `-CleanLegacy` (Windows) / `--clean-legacy` (Unix) removes everything in
the config directory. The `oc-product` wrapper lives outside it and must be
removed by hand.

## UI/TUI preferences

OpenCode keeps TUI-specific preferences separately from main provider config. If you have a personal `tui.json` you want to preserve, copy a **secret-free** version into this directory manually and commit it.

Do not copy a global provider config into Git unless you have inspected it and replaced every credential with environment/file references.
