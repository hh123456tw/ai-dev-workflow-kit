# New-computer restore checklist

- [ ] Clone this repository
- [ ] Install Git / Node / OpenCode
- [ ] Run the platform setup script (installs gstack and deploys the shared
      agents and commands — `stable-lead` plus the DeepSeek workers, and the
      `/stable` and `/gstack-*` commands)
- [ ] Confirm the global `opencode.jsonc` loads the Superpowers plugin and sets
      `"default_agent": "stable-lead"`. Without the plugin, the lead has no
      Superpowers skills.
- [ ] Configure provider authentication locally (`opencode auth login`;
      credentials are never in this repo)
- [ ] Verify `opencode models` shows `openai/gpt-5.6-sol` and
      `deepseek/deepseek-v4-flash`
- [ ] Verify `opencode debug skill` lists `test-driven-development`,
      `using-superpowers`, and `writing-plans`
- [ ] Verify `opencode debug config` resolves `default_agent` to `stable-lead`
- [ ] Open OpenCode with the stock shortcut and confirm the session starts as
      `stable-lead`
- [ ] Verify the lead resolves to the primary model and the bounded workers
      resolve to DeepSeek V4.1 Flash
- [ ] Verify the lead defaults to implementing directly and delegates at most one
      bounded worker, and only when all four delegation conditions hold
- [ ] Verify gstack skills are available post-integration
      (qa/review/ship/cso/investigate/plan-ceo-review/design-review/benchmark)
- [ ] Verify a worker handback includes changed files, exact commands and results,
      core acceptance result, and remaining limitation or blocker
- [ ] Verify workers cannot spawn subagents, cannot reach the web, cannot commit,
      push, merge, rebase, reset, or clean, and cannot read credential paths
- [ ] Verify read-only agents (`explorer`, `reviewer`) cannot edit
- [ ] Remove stale artifacts from earlier generations: the
      `team-lead` / `team-scout` / `team-builder` / `team-reviewer` agents, the
      `/team` command, `profiles/team*`, `profiles/product*`, `ensemble.json`,
      `ensemble.db*`, and the `oc-product` wrapper. Setup's `-CleanLegacy`
      (Windows) / `--clean-legacy` (Unix) removes most of these; see
      `desktop/opencode/README.md`
- [ ] Run a disposable RED -> GREEN -> verified handback smoke test
- [ ] Confirm compound learning fires: lead drafts learnings, user approves, the
      current project's AGENTS.md stays within the 40-line budget
