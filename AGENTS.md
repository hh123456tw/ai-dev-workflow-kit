# OpenCode Three-Mode Workflows

Three process-isolated modes. Mode isolation is config-level, not agent-level,
because plugin loading happens at the process/config layer.

## Modes

| Mode | Default agent | Superpowers | Purpose |
| --- | --- | --- | --- |
| Vanilla | `build` | full plugin + bootstrap | upstream reference and maximum rigor |
| Stable | `stable-lead` | full plugin + bootstrap | safe daily workflow and Core rollback |
| Core | `core-lead` | 6 curated skills, no bootstrap | autonomous Hackathon/MVP delivery |

The stock OpenCode shortcut and the global config resolve to Stable.

## Entry points

| Surface | Vanilla | Stable | Core |
| --- | --- | --- | --- |
| CLI | `oc-vanilla` | `oc-stable` | `oc-core` |
| Desktop shortcut | `OpenCode Vanilla` | stock `OpenCode` | `OpenCode Core` |

Desktop entries are alternative entries, not concurrent windows. Verified on
OpenCode Desktop 1.18.31: launching a second instance with a different
`--user-data-dir` exits immediately, because the single-instance lock is not
separated by that switch. Close the running Desktop instance before opening
another mode. The three CLI launchers are separate processes and can run
concurrently. The stock shortcut is never modified.

## Core skills

`test-driven-development`, `systematic-debugging`,
`verification-before-completion`, `requesting-code-review`,
`receiving-code-review`, `finishing-a-development-branch`.

Core must not expose `brainstorming`, `writing-plans`,
`subagent-driven-development`, or `using-git-worktrees`.

## Core behavior

- A clear specification means start implementing. No design-approval loop.
- Reversible ambiguity: pick the simplest reasonable default, record it, continue.
- Stop only for irreversible/destructive actions, security or credentials,
  destructive migrations, or access only the user can grant.
- Implement directly by default. Delegate one bounded DeepSeek worker only when
  file ownership, shared state, independent acceptance, and independent rollback
  all hold. At most one writer at a time.
- One read-only reviewer after a non-trivial multi-file change.
- Deterministic checks are the authority. Never claim PASS without executed evidence.
- Never start new work from a red baseline.

## Isolation contract

Core runs with `--pure`, its own `OPENCODE_CONFIG_DIR`, its own
`XDG_CONFIG_HOME`, `OPENCODE_DISABLE_EXTERNAL_SKILLS=1`, and
`OPENCODE_DISABLE_DEFAULT_PLUGINS=1`. Vanilla and Stable inherit the global
config directory and the full Superpowers plugin.

Core skills are copied at setup time from the installed Superpowers package and
are git-ignored. The repository pins the required Superpowers version (6.3.0)
and fails setup on a mismatch instead of silently falling back to the full plugin.

## Safety

- Never expose or commit credentials; credential paths are denied in every agent.
- Destructive git operations are denied; `git rebase` and `git push` ask first.
- Workers cannot spawn subagents, reach the web, commit, push, merge, rebase,
  reset, or clean.
- Escalate architecture, auth/payment/security, migration, and test-vs-spec
  conflicts instead of guessing.

## Verification

```powershell
pwsh -NoProfile -File tests/profile-bundle.acceptance.ps1
python -m pytest tests/test_profile_bundle.py -q
```

## Next stage (research only)

`docs/research/2026-09-19-jev-risk-routed-hybrid-core.md` proposes a
Risk-Routed Hybrid Core inside Core only. Not implemented; requires shadow
calibration and an A/B/C benchmark before any enforcement.
