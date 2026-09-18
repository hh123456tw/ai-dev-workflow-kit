# New-computer restore checklist

- [ ] Clone this repository
- [ ] Install Git / Node / OpenCode
- [ ] Run platform setup script (installs gstack, deploys the shared agents and
      commands — `stable-lead` plus the DeepSeek workers, and the `/stable` and
      `/gstack-*` commands — and installs the portable global `opencode.jsonc` +
      `gstack.jsonc` when missing)
- [ ] Configure provider authentication locally (`opencode auth login`;
      credentials are never in this repo)
- [ ] Confirm `.local/models.*` has verified IDs (defaults already filled)
- [ ] Verify `opencode models` shows `openai/gpt-5.6-sol` and
      `deepseek/deepseek-v4-flash`
- [ ] If `~/.config/opencode/opencode.jsonc` already existed, confirm setup warned
      instead of rewriting it. Remove any `@hueyexe/opencode-ensemble` entry from
      it by hand; the multi-agent layer is retired.
- [ ] Verify both entry surfaces resolve: the Desktop profile `profiles/product`
      via `oc-product`, and the `/stable` slash command
- [ ] Verify `oc-product` starts with `stable-lead` as the default agent
- [ ] Verify the lead resolves to GPT-5.6 and the bounded workers resolve to
      DeepSeek V4.1 Flash
- [ ] Verify the lead can see the gstack toolbox and Superpowers
- [ ] Verify the lead defaults to implementing directly and delegates at most one
      bounded worker, and only when all four delegation conditions hold
- [ ] Verify gstack skills are available only post-integration
      (qa/review/ship/cso/investigate/plan-ceo-review/design-review/benchmark)
- [ ] Verify a worker handback includes changed files, exact commands and results,
      core acceptance result, and remaining limitation or blocker
- [ ] Verify workers cannot spawn subagents, cannot reach the web, cannot commit,
      push, merge, rebase, reset, or clean, and cannot read credential paths
- [ ] Verify read-only agents (`explorer`, `reviewer`) cannot edit
- [ ] Remove stale deployed artifacts from earlier generations: the
      `team-lead` / `team-scout` / `team-builder` / `team-reviewer` agents, the
      `/team` command, the deployed `profiles/team*` entries, and
      `ensemble.json`; see `desktop/opencode/README.md`
- [ ] Reconnect Codex Desktop plugins/apps if used
- [ ] Run a disposable RED -> GREEN -> verified handback smoke test
- [ ] Confirm compound learning fires: lead drafts learnings, user approves, the
      current project's AGENTS.md stays within the 40-line budget
