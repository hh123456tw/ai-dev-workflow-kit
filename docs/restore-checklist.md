# New-computer restore checklist

- [ ] Clone this repository
- [ ] Install Git / Node / OpenCode
- [ ] Run the platform setup script
      (`scripts/setup-windows.ps1` or `scripts/setup-unix.sh`)
- [ ] Confirm the global `opencode.jsonc` loads the Superpowers plugin and sets
      `"default_agent": "stable-lead"`. Without the plugin, Stable has no
      Superpowers skills.
- [ ] Configure provider authentication locally (`opencode auth login`;
      credentials are never in this repo)
- [ ] Verify `opencode models` shows `openai/gpt-5.6-sol` and
      `deepseek/deepseek-v4-flash`
- [ ] Verify all three mode configs resolve the same model IDs
- [ ] Verify Vanilla resolves `build` with the full Superpowers skill set,
      including `brainstorming` and `subagent-driven-development`
- [ ] Verify Stable resolves `stable-lead` with the full Superpowers skill set
- [ ] Verify Core resolves `core-lead`, shows `plugin = (none)`, and lists exactly
      the six Core skills
- [ ] Verify Core does NOT list `brainstorming`, `writing-plans`,
      `subagent-driven-development`, or `using-git-worktrees`
- [ ] Verify `modes/core/skills/manifest.json` records Superpowers 6.3.0
- [ ] Verify `oc-vanilla`, `oc-stable`, and `oc-core` resolve on PATH
- [ ] Verify the stock OpenCode shortcut still opens Stable and was not modified
- [ ] Verify the `OpenCode Vanilla` and `OpenCode Core` shortcuts exist
- [ ] Confirm the Desktop single-instance limitation: with one Desktop instance
      running, launching another exits immediately. Only one Desktop instance runs
      at a time, so close it before switching modes. The CLI launchers are
      unaffected and can run concurrently.
- [ ] Confirm the global `opencode.jsonc` still sets `"default_agent":
      "stable-lead"` so the stock shortcut runs Stable
- [ ] Run one headless smoke task per mode and confirm public and hidden
      acceptance pass
- [ ] Confirm Core produces no planning or SDD artifacts
- [ ] Confirm Core worker handback includes changed files, exact commands and
      results, core acceptance result, and remaining limitation or blocker
- [ ] Confirm workers cannot spawn subagents, reach the web, commit, push, merge,
      rebase, reset, or clean, and cannot read credential paths
- [ ] Confirm read-only agents (`explorer`, `reviewer`) cannot edit
- [ ] Remove stale artifacts from earlier generations if present:
      `team-lead` / `team-scout` / `team-builder` / `team-reviewer` agents,
      `/team`, `profiles/`, `ensemble.*`, and the `oc-product` wrapper.
      Setup lists them; `-CleanLegacy` / `--clean-legacy` removes them.
- [ ] Confirm compound learning fires: lead drafts learnings, user approves, the
      current project's AGENTS.md stays within the 40-line budget
