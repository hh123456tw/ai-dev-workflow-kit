# OpenCode Desktop / TUI rebuild

The tracked config files are portable. Provider authentication is not.

## How this repo is actually used

Open OpenCode normally (the stock shortcut) and run `/stable <request>`. No
profile switch, no special launcher. The lead definition is deployed to the global
agents directory, and Superpowers is loaded by the global config's plugin entry.

`oc-product` is an optional wrapper: it points `OPENCODE_CONFIG` at
`profiles/product/opencode.jsonc` so model routing comes from
`.local/models.*` instead of the global config. Use it when you want the
portable model file to win.

There is no OpenCode "profile" feature. OpenCode has no `profiles/` support in
its codebase; the directory is this repo's own convention, and only
`oc-product` reads it.

## Layout

| Path | Purpose |
| --- | --- |
| `agents/stable-lead.md` | The single lead definition, deployed globally. |
| `agents/explorer.md`, `agents/implementer.md`, `agents/reviewer.md`, `agents/test-writer.md` | Bounded DeepSeek workers, deployed globally. |
| `commands/stable.md`, `commands/gstack-*.md` | The `/stable` and namespaced gstack commands. |
| `profiles/product/opencode.jsonc` | Optional config used only by `oc-product`. |
| `global/opencode.jsonc` | Portable global config installed when none exists. |

## Rebuild

1. Install OpenCode.
2. Authenticate the same providers locally.
3. Run `scripts/setup-windows.ps1` or `scripts/setup-unix.sh`.
4. Use `/models` and copy actual model IDs into the ignored `.local/models.*` file.
5. Open OpenCode and run `/stable`, or use `oc-product`.

## Remove stale deployed artifacts

Earlier generations deployed a multi-agent Team workflow, a Team profile, and a
Desktop profile file. All of that is retired. Delete these from the deployed
OpenCode config directory (for example `%USERPROFILE%\.config\opencode\` on
Windows or `~/.config/opencode/` on macOS/Linux):

- `agents/team-lead.md`, `agents/team-scout.md`, `agents/team-builder.md`,
  `agents/team-reviewer.md`
- `commands/team.md`
- `profiles/team.json` and the whole `profiles/team/` directory
- `profiles/product.json` and `profiles/product/` (the retired Desktop profile
  shape; `oc-product` reads the repo copy, not these)
- `ensemble.json`, `ensemble.db`, `ensemble.db-shm`, `ensemble.db-wal`
- any `@hueyexe/opencode-ensemble` entry still present in the global
  `opencode.jsonc`

Setup offers `-CleanLegacy` (Windows) / `--clean-legacy` (Unix) to remove the
first group automatically. The rest must be removed by hand.

## UI/TUI preferences

OpenCode keeps TUI-specific preferences separately from main provider config. If you have a personal `tui.json` you want to preserve, copy a **secret-free** version into this directory manually and commit it.

Do not copy a global provider config into Git unless you have inspected it and replaced every credential with environment/file references.
