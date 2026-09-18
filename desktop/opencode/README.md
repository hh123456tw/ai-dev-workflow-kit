# OpenCode Desktop / TUI rebuild

The tracked profile files are portable. Provider authentication is not.

## Current profile layout

There is one workflow and one profile:

| Path | Purpose |
| --- | --- |
| `profiles/product/opencode.jsonc` | The profile config: model env vars, `default_agent: stable-lead`, the Superpowers plugin, and permissions. |
| `agents/stable-lead.md` | The single lead definition, deployed globally and reused by the profile. |
| `agents/explorer.md`, `agents/implementer.md`, `agents/reviewer.md`, `agents/test-writer.md` | Bounded DeepSeek workers, deployed globally. |
| `commands/stable.md`, `commands/gstack-*.md` | The `/stable` and namespaced gstack commands. |

The profile deliberately has no agents directory and no `instructions` file. The
lead definition lives in one place and every entry surface resolves to it, so
there is no second copy to keep in sync.

Because the profile resolves `stable-lead` from the globally deployed agents, run
the setup script before launching `oc-product`. A profile launch without the
global agents deployed will fail to resolve the default agent.

## Rebuild

1. Install OpenCode.
2. Authenticate the same providers locally.
3. Run `scripts/setup-windows.ps1` or `scripts/setup-unix.sh`.
4. Use `/models` and copy actual model IDs into the ignored `.local/models.*` file.
5. Start `oc-product`, or use `/stable` in any project.

## Remove stale deployed artifacts

Earlier generations deployed a multi-agent Team workflow and its profile. That
workflow is retired. Delete these from the deployed OpenCode config directory
(for example `%USERPROFILE%\.config\opencode\` on Windows or
`~/.config/opencode/` on macOS/Linux):

- `agents/team-lead.md`, `agents/team-scout.md`, `agents/team-builder.md`,
  `agents/team-reviewer.md`
- `commands/team.md`
- `profiles/team.json` and the whole `profiles/team/` directory
- `ensemble.json`
- any `@hueyexe/opencode-ensemble` entry still present in the global
  `opencode.jsonc`

None of these are recreated by the current setup script. Removing them is safe.

## UI/TUI preferences

OpenCode keeps TUI-specific preferences separately from main provider config. If you have a personal `tui.json` you want to preserve, copy a **secret-free** version into this directory manually and commit it.

Do not copy a global provider config into Git unless you have inspected it and replaced every credential with environment/file references.
