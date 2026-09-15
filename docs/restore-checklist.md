# New-computer restore checklist

- [ ] Clone this repository
- [ ] Install Git / Node / OpenCode
- [ ] Run platform setup script (deploys Matt skills, gstack, ensemble.json,
      shared agents/commands, portable global opencode.jsonc, gstack.jsonc)
- [ ] Configure provider authentication locally (`opencode auth login`;
      credentials are never in this repo)
- [ ] Confirm `.local/models.*` has verified IDs (defaults already filled)
- [ ] Verify `opencode models` shows `openai/gpt-5.6-sol` and
      `deepseek/deepseek-v4-flash`
- [ ] Verify `/stable` and `/team` commands resolve (stable-lead / team-lead)
- [ ] Verify `oc-product` starts PRODUCT mode
- [ ] Verify PRODUCT primary = GPT-5.6 Sol and PRODUCT worker = DeepSeek V4.1 Flash
- [ ] Verify PRODUCT can see gstack toolbox and Superpowers
- [ ] Verify `oc-team` starts orchestrator
- [ ] Verify TEAM allows selective gstack skills only post-integration
      (qa/review/ship/cso/investigate/plan-ceo-review/design-review/benchmark)
- [ ] Verify TEAM never loads Superpowers
- [ ] Verify ds-worker cannot edit tests
- [ ] Verify ds-worker cannot spawn subagents
- [ ] Verify reviewer is read-only
- [ ] Reconnect Codex Desktop plugins/apps if used
- [ ] Run TEAM disposable RED → GREEN → review smoke test
