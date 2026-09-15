# New-computer restore checklist

- [ ] Clone this repository
- [ ] Install Git / Node / OpenCode
- [ ] Run platform setup script
- [ ] Configure provider authentication locally
- [ ] Use OpenCode `/models` to resolve actual GPT-5.6 Sol ID
- [ ] Resolve actual DeepSeek V4.1 Flash ID
- [ ] Fill ignored `.local/models.*`
- [ ] Verify `oc-product` starts PRODUCT mode
- [ ] Verify PRODUCT primary = GPT-5.6 Sol and PRODUCT worker = DeepSeek V4.1 Flash
- [ ] Verify PRODUCT can see `gstack-*` and Superpowers
- [ ] Verify `oc-team` starts orchestrator
- [ ] Verify TEAM cannot load gstack skills
- [ ] Verify ds-worker cannot edit tests
- [ ] Verify ds-worker cannot spawn subagents
- [ ] Verify reviewer is read-only
- [ ] Reconnect Codex Desktop plugins/apps if used
- [ ] Run TEAM disposable RED → GREEN → review smoke test
