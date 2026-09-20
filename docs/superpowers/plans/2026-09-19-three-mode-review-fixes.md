# Three-Mode Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close every finding from the independent review of commit `4c1966d`, then deploy and verify the three isolated OpenCode workflow modes end to end.

**Architecture:** The three modes (Vanilla, Stable, Core) are config-isolated. Core uses its own `OPENCODE_CONFIG_DIR` and isolated config root, plus `--pure` on the two CLI launchers, so it cannot load the full Superpowers plugin or external skills; it keeps default provider plugins enabled so the pinned model resolves. Vanilla and Stable inherit the global config directory and the full Superpowers plugin.

**Tech Stack:** OpenCode 1.18.31 CLI and Desktop, PowerShell 5.1 and Bash launchers, Superpowers 6.3.0, pytest, PowerShell acceptance scripts.

**Spec:** `docs/superpowers/specs/2026-09-19-three-mode-opencode-workflows-design.md`

## Global Constraints

- Exactly three modes: Vanilla, Stable, Core. No fourth mode.
- Vanilla and Stable load the full `superpowers@git+https://github.com/obra/superpowers.git` plugin. Core loads no plugin.
- Core exposes exactly these six skills: `test-driven-development`, `systematic-debugging`, `verification-before-completion`, `requesting-code-review`, `receiving-code-review`, `finishing-a-development-branch`.
- Core must not expose `brainstorming`, `writing-plans`, `subagent-driven-development`, or `using-git-worktrees`.
- All three modes pin `model: openai/gpt-5.6-sol` and `small_model: deepseek/deepseek-v4-flash`.
- Required Superpowers version is `6.3.0`. A mismatch must fail setup loudly; never silently fall back to the full plugin.
- The stock OpenCode shortcut and the user's global `opencode.jsonc` must never be overwritten.
- Credential paths are denied in every agent, including both primary agents.
- Setup must be idempotent and must never touch provider credentials.
- Desktop single-instance is a verified limitation: only one Desktop instance runs at a time. No artifact may claim concurrent Desktop instances.
- Repository acceptance commands: `pwsh -NoProfile -File tests/profile-bundle.acceptance.ps1` and `python -m pytest tests/test_profile_bundle.py -q`.

---

### Task 1: Close the applied review fixes and remaining gaps

**Files:**
- Verify and finalize: `scripts/setup-windows.ps1`, `scripts/setup-unix.sh`, `scripts/oc-vanilla.ps1`, `scripts/oc-stable.ps1`, `scripts/oc-vanilla.sh`, `scripts/oc-stable.sh`, `scripts/desktop-vanilla.ps1`, `scripts/desktop-core.ps1`, `scripts/opencode-desktop-common.ps1`, `scripts/verify-modes.ps1`, `agents/stable-lead.md`, `modes/core/agents/core-lead.md`, `tests/profile-bundle.acceptance.ps1`, `tests/test_profile_bundle.py`, `docs/restore-checklist.md`, `desktop/opencode/README.md`

**Interfaces:**
- Consumes: the review findings against commit `4c1966d`.
- Produces: one commit on `main` containing the review fixes, plus a written verdict per finding.

**Applied already in the working tree (verify, do not redo):**
1. Setup installs `global/opencode.jsonc` when missing and warns when present (fixes the fresh-machine gap).
2. Setup backup covers CLI shims and the two managed shortcuts, and excludes the isolated XDG root.
3. Setup version discovery prefers the pinned `6.3.0` and otherwise returns the newest for a clear error.
4. `agents/stable-lead.md` and `modes/core/agents/core-lead.md` deny credential-path reads.
5. `oc-vanilla` and `oc-stable` (both PowerShell and Bash) clear `OPENCODE_DISABLE_EXTERNAL_SKILLS` and `OPENCODE_DISABLE_DEFAULT_PLUGINS`. They deliberately do **not** clear or set `XDG_CONFIG_HOME`: it is a legitimate user configuration choice, not a Core-only isolation flag, and the tests forbid naming it in those launchers.
6. Desktop wrappers log failures to `%LOCALAPPDATA%\OpenCode\mode-launcher.log` and show a message box instead of failing silently.
7. `scripts/verify-modes.ps1` performs runtime isolation checks instead of grepping launcher text.
8. `docs/restore-checklist.md`, `desktop/opencode/README.md`, `README.md`, and `AGENTS.md` state the Desktop single-instance limitation instead of claiming concurrent instances.
9. `setup-unix.sh` marks the launchers executable.
10. The stray `modes/core/.gitignore` produced by probe runs is deleted.

- [ ] **Step 1: Independently verify each applied fix**

For each of the ten items above, read the current file and confirm the fix is present and correct. Report any item that is missing, partial, or wrong. Do not trust this list; check the files.

- [ ] **Step 2: Resolve the `subagent_depth` question**

`modes/core/opencode.jsonc` sets `subagent_depth: 1`, and the acceptance test asserts it. Determine whether OpenCode 1.18.31 recognizes that key. Use `opencode debug config --pure` with the Core environment and inspect the resolved output. If the key is not recognized, remove it from the config and from the test assertion, and note the removal in the report. If it is recognized, keep it and say so with the evidence.

- [ ] **Step 3: Strengthen the weakest test assertions**

Fix these specific weaknesses:
- The stock-shortcut safety assertion matches a `Write-Host` string, so a setup that modified the shortcut but printed the sentence would pass. Add a real assertion that the stock shortcut path is absent from the deletion list.
- The version-mismatch path is untested. Add an assertion that the setup script contains a version comparison against `6.3.0` and an explicit failure, and that there is no branch that silently installs the full plugin as a fallback.
- `tests/test_profile_bundle.py` uses an unanchored `assertIn("model: deepseek/deepseek-v4-flash", ...)`; anchor it to a line, matching the PowerShell test.
- Validate the Core skill manifest contents (version plus the six skill names) in at least one test.

- [ ] **Step 4: Run both acceptance suites**

```powershell
pwsh -NoProfile -File tests/profile-bundle.acceptance.ps1
python -m pytest tests/test_profile_bundle.py -q
```

Both must pass. Also confirm the PowerShell parser reports zero errors for every changed `.ps1` file and that `bash -n` passes for every changed `.sh` file.

- [ ] **Step 5: Commit**

Commit the review fixes as one commit on `main`. Report the commit hash and the exact test output.

**Report:** write the full report to `.superpowers/sdd/2026-09-19-three-mode-review-fixes/task-1-report.md`, including a verdict line per review finding (`closed`, `parked`, or `not applicable`) with the file and line evidence.

---

### Task 2: Deploy and verify the three modes end to end

**Files:**
- Verify: the deployed state under `~/.config/opencode/modes/`, the global agents and commands, `~/bin/oc-*.cmd`, and the four shortcuts.

**Interfaces:**
- Consumes: the committed fixes from Task 1.
- Produces: executed verification evidence.

- [ ] **Step 1: Re-run Windows setup**

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/setup-windows.ps1
```

Expected: exit 0, all six steps report success, the stock shortcut is untouched, and the global `opencode.jsonc` is left untouched because it already exists (a warning is acceptable).

- [ ] **Step 2: Run runtime isolation verification**

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify-modes.ps1
```

Expected: `MODE_ISOLATION_PASS`, exit 0. Record the full output.

- [ ] **Step 3: Confirm setup idempotency**

Re-run setup a second time. Expected: exit 0, no duplicate shortcuts, no duplicated launcher entries, and the number of shortcuts on the Desktop and Start Menu is unchanged.

- [ ] **Step 4: Headless behavior smoke, one task per mode**

Run a small deterministic bugfix task through each mode and confirm: the root session agent matches the requested mode, public tests pass, and the hidden acceptance check passes. For Core, also confirm no planning or SDD artifact files are produced.

If the primary model is rate limited, stop and report the blocker with the exact error. Do not substitute a different model, because that would invalidate the comparison.

- [ ] **Step 5: Desktop wrapper verification**

With one Desktop instance running, launch the Vanilla and Core wrappers. Expected: the second launch exits without corrupting the running instance, and any failure is written to `%LOCALAPPDATA%\OpenCode\mode-launcher.log` rather than being swallowed. Do not close the user's running Desktop instance.

- [ ] **Step 6: Report**

Write the full report to `.superpowers/sdd/2026-09-19-three-mode-review-fixes/task-2-report.md` with exact commands, exact output, and any blocker.
