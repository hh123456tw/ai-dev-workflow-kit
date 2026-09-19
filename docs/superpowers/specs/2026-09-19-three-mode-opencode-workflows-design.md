# Three-Mode OpenCode Workflows Design

**Date:** 2026-09-19  
**Status:** Approved design; implementation not started  
**Scope:** OpenCode CLI and Desktop on Windows, plus CLI launchers on Unix

## 1. Goal

Allow three measured development workflows to coexist without sharing behavior-changing configuration:

| Mode | Purpose | Default agent | Superpowers behavior |
| --- | --- | --- | --- |
| Vanilla | Full upstream reference and maximum process rigor | OpenCode `build` | Full plugin/bootstrap |
| Stable | Safe current workflow and rollback | `stable-lead` | Full plugin/bootstrap plus cost-control policy |
| Core | Fast autonomous Hackathon/MVP workflow | `core-lead` | Curated skills only; no bootstrap/gates |

The existing stock OpenCode shortcut remains Stable. Core is introduced as a canary rather than replacing Stable immediately.

## 2. Benchmark Basis

The architecture follows a reproducible benchmark using three tasks:

1. Greenfield multi-module expenses CLI.
2. Cross-module feature in an existing inventory project.
3. Regression bugfix in an existing scheduler.

Agents saw the specifications and public tests but not hidden acceptance tests. Every valid run passed public and hidden tests without modifying existing tests.

| Workflow | Runs | Pass | Mean time | Session topology | Mean DeepSeek cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| Vanilla | 3 | 3/3 | 18m 26s | 2–17 sessions | $0.0988 |
| Stable | 9 | 9/9 | 9m 52s | fixed 2 sessions | $0.0170 |
| Core | 9 | 9/9 | 6m 5s | fixed 2 sessions | $0.0163 |

Relative to Stable, Core was 38.3% faster, used 37.7% fewer input tokens and 47.6% fewer output tokens, and had the same observed 9/9 hidden-test success rate. This is sufficient for a canary, not proof of a production failure rate.

Raw benchmark artifacts are stored outside the repository at `workflow-benchmark-20260918.zip` on the user's Desktop.

## 3. Isolation Requirement

The three modes cannot be implemented as agent choices in one OpenCode process.

- Vanilla and Stable require the full Superpowers plugin and runtime bootstrap.
- Core must not load the bootstrap or the heavy skills (`brainstorming`, `writing-plans`, `subagent-driven-development`, `using-git-worktrees`).
- Plugin loading occurs at the process/config level, not at the agent level.

Therefore each mode gets a separate config and launcher.

## 4. Repository Layout

```text
modes/
├─ vanilla/
│  └─ opencode.jsonc
├─ stable/
│  └─ opencode.jsonc
└─ core/
   ├─ opencode.jsonc
   └─ agents/
      └─ core-lead.md

scripts/
├─ oc-vanilla.ps1
├─ oc-vanilla.sh
├─ oc-stable.ps1
├─ oc-stable.sh
├─ oc-core.ps1
├─ oc-core.sh
├─ desktop-vanilla.ps1
├─ desktop-core.ps1
├─ setup-windows.ps1
└─ setup-unix.sh
```

Shared bounded workers remain the source files under `agents/`. Setup deploys copies into each mode where needed so agent definitions cannot leak across modes.

## 5. Mode Definitions

### 5.1 Vanilla

- Primary model: `openai/gpt-5.6-sol`.
- Worker model: `deepseek/deepseek-v4-flash`.
- Default agent: OpenCode `build`.
- Loads the full `superpowers@git+https://github.com/obra/superpowers.git` plugin.
- Retains upstream brainstorming, writing-plans, TDD, SDD, worktree, review, and verification behavior.
- Exists as a reference and maximum-rigor fallback, not the daily default.

### 5.2 Stable

- Same models and full Superpowers plugin as Vanilla.
- Default agent: `stable-lead`.
- Keeps the existing one-writer policy, four delegation conditions, evidence-based handback, deadline modes, and final reviewer.
- Remains the stock OpenCode shortcut and the immediate rollback for Core.

### 5.3 Core

- Same primary and worker models.
- Default agent: `core-lead`.
- No Superpowers plugin/bootstrap.
- Loads exactly six selected skills:
  - `test-driven-development`
  - `systematic-debugging`
  - `verification-before-completion`
  - `requesting-code-review`
  - `receiving-code-review`
  - `finishing-a-development-branch`
- Does not expose `brainstorming`, `writing-plans`, `subagent-driven-development`, or `using-git-worktrees`.
- Starts implementation immediately when a specification is clear.
- Chooses and records reversible defaults rather than stopping for approval.
- Stops only for irreversible/destructive actions, security/credentials, or destructive data migrations.
- Implements directly by default and uses one bounded DeepSeek implementer only when ownership and acceptance are independent.
- Uses one final read-only reviewer for non-trivial multi-file changes.

## 6. Core Skill Deployment

Core skills are not vendored into this repository.

Windows/Unix setup must:

1. Locate the installed Superpowers package.
2. Require the expected tested version (`6.3.0`) unless the repository is deliberately updated.
3. Copy only the six selected skill directories to the deployed Core config directory.
4. Fail clearly if the package or version is missing; never silently load the full plugin as a fallback.
5. Record the deployed upstream version in a generated manifest.

The repository retains the skill names and version requirement, not third-party source code.

## 7. CLI Entry Points

| Command | Mode |
| --- | --- |
| `oc-vanilla` | Vanilla config, full Superpowers, `build` |
| `oc-stable` | Stable config, full Superpowers, `stable-lead` |
| `oc-core` | Core config, `--pure`, selected skills, `core-lead` |

Every continuation or automated run must explicitly carry both session ID and agent. OpenCode 1.18.31 was observed to switch `--continue` calls to `default_agent` when the agent is not repeated.

## 8. OpenCode Desktop

### 8.1 Verified Desktop behavior

Inspection of the installed OpenCode Desktop 1.18.31 `app.asar` confirmed:

- The sidecar inherits `process.env`, including `OPENCODE_CONFIG` and `OPENCODE_CONFIG_DIR`.
- The app calls `requestSingleInstanceLock()`.
- Electron receives `--user-data-dir` before the lock is acquired.
- An isolated `XDG_CONFIG_HOME` prevents Core from reading the global full-plugin config.

CLI simulation of the planned Core Desktop environment confirmed that only the six Core skills are visible and the heavy skills/bootstrap are absent.

### 8.2 Desktop entries

| Shortcut | Mode | User data directory |
| --- | --- | --- |
| Existing `OpenCode` | Stable | `%APPDATA%\ai.opencode.desktop` |
| `OpenCode Vanilla` | Vanilla | `%APPDATA%\ai.opencode.desktop-vanilla` |
| `OpenCode Core` | Core | `%APPDATA%\ai.opencode.desktop-core` |

The existing Stable shortcut must remain byte-for-byte unchanged.

Vanilla and Core shortcuts target PowerShell wrapper scripts. The wrappers set mode-specific environment variables and start the installed `OpenCode.exe` with the matching `--user-data-dir`.

Core additionally sets:

```text
OPENCODE_CONFIG=<deployed Core config>
OPENCODE_CONFIG_DIR=<deployed Core config dir>
XDG_CONFIG_HOME=<isolated Core config root>
OPENCODE_DISABLE_EXTERNAL_SKILLS=1
```

Core deliberately does **not** set `OPENCODE_DISABLE_DEFAULT_PLUGINS`. That switch
removes OpenCode's built-in provider plugins, including the OpenAI provider, so
`openai/gpt-5.6-sol` fails to resolve at runtime with
`ProviderModelNotFoundError`. `--pure` plus the isolated config dir and config
root already exclude the Superpowers plugin, so the default provider plugins must
stay enabled for the pinned model to load. Vanilla and Stable clear the variable
so a value exported by a parent shell cannot leak into them.

Provider authentication remains shared because the data/auth path is not changed.

### 8.2.1 Verified limitation: one Desktop instance at a time

The original design claimed all three Desktop entries could run simultaneously. That
claim is **wrong for OpenCode Desktop 1.18.31** and was removed after direct testing.

Observed on 2026-09-19, with the stock instance running:

- Launching `OpenCode.exe --user-data-dir=<fresh dir>` exits immediately with code 0.
- The fresh user-data directory stays completely empty.
- The default `%APPDATA%\ai.opencode.desktop\lockfile` is not modified.
- Reproduced with three different target directories and both
  `--user-data-dir=<path>` and `--user-data-dir <path>` argument forms.

The app calls `app.requestSingleInstanceLock()` with no options and exits when it
fails. On this build the lock is not separated by `--user-data-dir`, so a second
Desktop instance cannot start while another is running.

Consequences:

- The three Desktop shortcuts are **alternative entries, not concurrent windows**.
  Only one Desktop instance runs at a time; close it before opening another mode.
- The three **CLI** launchers are unaffected and can run concurrently, because they
  are separate processes with their own config and environment.
- Core's config isolation is still verified and effective for both the CLI launcher
  and the Desktop wrapper; only concurrency is unavailable.

### 8.3 Desktop limitations

- Only one Desktop instance at a time, as verified in §8.2.1.
- Session history is separate per mode, because each mode uses its own user-data
  directory whenever it is the running instance.
- `opencode://` deep links route to whichever instance is running.
- An OpenCode Desktop update can change Electron launch behavior; re-verify if a
  shortcut stops isolating correctly.

## 9. Setup Behavior

### 9.1 Windows

`setup-windows.ps1` must:

1. Back up the global config, agents, commands, managed mode directories, wrappers, and custom shortcuts.
2. Deploy shared agents and commands.
3. Deploy the three mode configs and mode-specific agents.
4. Deploy the six Core skills and version manifest.
5. Install `oc-vanilla`, `oc-stable`, and `oc-core` CLI launchers.
6. Create Start Menu and Desktop shortcuts for `OpenCode Vanilla` and `OpenCode Core`.
7. Leave the existing stock OpenCode shortcut unchanged.
8. Be idempotent: reruns update managed files and never duplicate shortcuts.

### 9.2 Unix

`setup-unix.sh` deploys the three CLI launchers and mode configs. It does not create Desktop shortcuts.

### 9.3 Ownership

Setup may modify only files declared as managed by this repository. It must not overwrite provider credentials, unrelated MCP/provider configuration, or the stock OpenCode shortcut.

## 10. Verification Gates

Nothing is committed/pushed as complete until every gate is green.

### 10.1 Static and syntax

- All JSON/JSONC configs parse.
- PowerShell parser reports zero errors.
- `bash -n` passes.
- All three modes resolve the same model IDs.

### 10.2 Skill and agent isolation

- Vanilla sees full Superpowers, including brainstorming and SDD, and defaults to `build`.
- Stable sees full Superpowers and defaults to `stable-lead`.
- Core sees exactly the selected Core skills and does not see brainstorming, writing-plans, SDD, or the Superpowers bootstrap.
- Core cannot resolve an undeclared global/profile agent by accident.

### 10.3 Headless behavior smoke

- Run a fixed task through each mode.
- Public and hidden acceptance tests pass.
- Session root agent matches the requested mode.
- Core produces no planning/SDD artifacts.
- No existing tests are modified or weakened.

### 10.4 Desktop smoke

**Revised after the §8.2.1 finding.** The coexistence check is not achievable on
OpenCode Desktop 1.18.31. The gate becomes:

- Verify the Core and Vanilla wrappers resolve the correct mode config, agent, and
  skill set when their environment is applied (already covered by §10.2).
- Verify the stock shortcut is unchanged.
- Verify that launching a second Desktop instance exits cleanly and leaves the
  running instance intact, rather than corrupting state.
- Verify the three CLI launchers run as independent concurrent processes.

### 10.5 Regression and review

- Repository acceptance tests pass.
- Existing Stable behavior remains unchanged.
- Provider auth is not copied, modified, or committed.
- Independent review checks config isolation, shortcut safety, setup idempotency, version handling, and secret boundaries.
- All Critical/Important findings are fixed and all affected gates rerun.

## 11. Delivery

After all gates pass:

1. Inspect `git status`, diff, and recent history.
2. Commit only intentional repository changes.
3. Push to `main` as explicitly requested.
4. Report the commit hash, test evidence, installed CLI launchers, installed Desktop shortcuts, and any residual limitations.

## 12. Canary and Rollback

- Stock OpenCode remains Stable.
- Use Core for three real Hackathon/MVP tasks.
- If Core passes all three without regression, consider making Core the stock default in a separate decision.
- Rollback is immediate: close Core and open the existing Stable shortcut or run `oc-stable`.
- Vanilla remains available for upstream reference and maximum-rigor comparison.
