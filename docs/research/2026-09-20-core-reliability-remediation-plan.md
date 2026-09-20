# Core Reliability Remediation Plan

**Date:** 2026-09-20  
**Status:** Phases 1–2 implemented and verified; Phases 3–4 not started; Jev routing remains out of scope  
**Basis:** [Core real-task baseline](2026-09-20-core-real-task-baseline.md)

## Decision

Do not begin Static Hybrid or Jev routing work yet. The baseline achieved 5/6 strict
successes but 0/6 first-pass successes, and every valid task made an incorrect
completion claim. The immediate objective is to make Core's completion evidence
reliable before changing which model implements a task.

## Scope and non-goals

This work changes only Core completion, review, and evidence rules plus their
configuration-level acceptance tests. It does not change mode isolation, add a
router, obtain TypeSafe credentials, add a fourth mode, or modify Stable/Vanilla.

## Phase 1 — Make completion gates non-bypassable

**Owner files:**

- `modes/core/agents/core-lead.md`
- `AGENTS.md`
- `tests/test_profile_bundle.py`
- `tests/profile-bundle.acceptance.ps1`

**Changes:**

1. Use a deadline-aware gate. Build requires the read-only `reviewer` subagent at
   two or more production files. Feature Freeze and Demo Survival require both that
   file-count threshold and at least one named risk flag. The `explorer` cannot
   substitute. Every changed file must be classified and every flag recorded with
   affected paths before `review_not_required` is valid.
2. A reviewer dispatch failure, denial, timeout, or missing result is a
   `verification_blocked` outcome, never a successful completion. Core may report
   the implementation and deterministic-check evidence, but must explicitly state
   that final completion is blocked and must not claim done.
3. Require all Important/Critical reviewer findings to be resolved and reverified
   before completion. A follow-up review is required when the remediation changes
   the reviewed behavior materially.
4. Require a completion receipt: deadline mode, changed-file count and
   classifications, risk flags with affected paths, review trigger, commands with
   their exact result and exit codes, acceptance coverage, reviewer status/findings,
   scope statement, and any blocked condition. Missing fields mean the task remains
   incomplete, and a required review may never be recorded as "not required".

**Acceptance:** static profile tests prove the policy contains each gate, and the
profile-bundle acceptance script confirms Core still exposes only the approved six
skills and reviewer permission remains available.

## Phase 2 — Prevent false-green verification

**Owner files:** same as Phase 1.

**Changes:**

1. For a numeric, performance, concurrency, cache, or resource acceptance
   criterion, require an independent measurement that exercises the real command,
   API, or execution path named by the request.
2. Prohibit using mocked clocks, synthetic counters, implementation internals, or
   self-authored substitute metrics as proof for a real-world metric unless the
   request explicitly defines that substitute metric.
3. Record the measurement input/fixture size, command, threshold, observed value,
   and exit code in the completion receipt.
4. Require a regression test for every correction prompted by a reviewer finding
   that changes behavior.

**Acceptance:** profile tests cover the required language; a focused fixture test
asserts that the Core policy rejects a synthetic metric as performance evidence.

## Implementation record (Phases 1–2)

Changed files:

- `modes/core/agents/core-lead.md` — new "Real-path evidence" section; "Review"
  section now carries deadline-aware file-count plus named-risk triggers,
  per-file/flag evidence, the "authoritative for what they cover, but not sufficient
  for completion" rule, and the reviewer-correction regression-test rule; new
  "Completion gate" section with the receipt fields and `verification_blocked`.
- `AGENTS.md` — Core behavior bullets updated to match, including the completion
  receipt and the removal of the unqualified "deterministic checks are the
  authority" claim.
- `README.md` — the Chinese Core behavior list updated for the same rules.
- `tests/test_profile_bundle.py` — three policy tests
  (`test_core_completion_gate_policy_requirements`,
  `test_core_review_trigger_is_objective_and_findings_block`,
  `test_core_requires_real_path_measurement_evidence`) plus a `section()` helper
  that scopes assertions to a named markdown section.
- `tests/profile-bundle.acceptance.ps1` — mirrored `Get-Section` helper and gate
  assertions.
- `scripts/smoke-core-reviewer-blocked.ps1` — creates an isolated temporary Core
  profile, explicitly denies only `reviewer`, keeps `explorer` available to exercise
  the substitution regression, and runs a two-production-file task with `--auto`.
  Its JSONL validator accepts only `final_answer` text, accepts only an explicitly
  denied reviewer task event (or no event when the denied tool is hidden), rejects
  substitute task agents and nested-OpenCode fallbacks, and requires
  `verification_blocked` plus an explicit refusal to claim completion. The real
  deployed profile is not modified.

Executed evidence:

- `python -m pytest tests/test_profile_bundle.py -q` -> 15 passed
- `pwsh -NoProfile -File tests/profile-bundle.acceptance.ps1` -> `THREE_MODE_ACCEPTANCE_PASS`
- `pwsh -NoProfile -File scripts/verify-modes.ps1` -> `MODE_ISOLATION_PASS`
- `pwsh -NoProfile -File scripts/smoke-core-reviewer-blocked.ps1 -SelfTest`
  -> `CORE_REVIEWER_BLOCKED_SELFTEST_PASS`; fixtures prove intermediate text and
  skill-output keywords are ignored, while explorer substitution, invalid reviewer
  events, nested OpenCode, and positive final completion claims are rejected without
  a model call.
- `pwsh -NoProfile -File scripts/smoke-core-reviewer-blocked.ps1 -KeepArtifacts`
  produced valid blocked evidence in session `ses_f40d3250effea5QKdXlfX6MtBm`;
  implementation tests passed 3/3, no substitute task subagent or nested OpenCode
  was used, and the sole `final_answer` recorded Build mode, three changed files,
  per-file production classification, all risk flags, exact command results, scope,
  and `verification_blocked` without claiming completion. The initial parser rejected
  the equivalent phrase `Changed files: 3`; after replacing that brittle wording
  check with semantic alternatives, replaying the captured JSONL returned
  `CAPTURED_LIVE_EVIDENCE_PASS` without another model call. Artifact directory:
  `C:\Users\cygnu\AppData\Local\Temp\opencode-core-reviewer-blocked-22052-871538f976e64f9eb321ada43fd575d2`.
- Mutation checks (all failed as required, then reverted): renaming the
  "## Completion gate" heading; negating the `verification_blocked` copula;
  replacing "two or more production files" with a subjective phrase.

Independent review: one read-only reviewer, no Critical findings. Its five
Important findings were addressed: objective review trigger (C02 bypass closed),
unscoped/under-covering assertions tightened to include "returns no result",
"implementation internals", and the numeric record fields, AGENTS.md/README drift
removed, and the polarity-blind assertions replaced with contiguous-sentence
checks that fail when the rule is inverted. Minor findings M1 (regression-test rule
moved to the Review section with a behavior qualifier), M2 (authority wording),
M4, and M5 (receipt now asks for exact result *and* exit codes) were also applied.
M3 (Python `re` is case-sensitive while PowerShell `-match` is not) was left as
is: the mismatch can only produce a loud pytest failure, not a silent pass.

A later final review found two Important gaps: deterministic tests did not pin each
deadline mode to its exact risk-flag set, and the smoke's positive-completion scan
both rejected legitimate test-status wording and missed residual claims such as
`All done` or `Ready to ship`. Exact mapping assertions and behavior-focused parser
fixtures now close both gaps. The same revision added the no-deadline Build default
and reviewer permission assertions, boundary-safe risk-flag matching, denied-event
negative fixtures, and removed stale optional-review and subjective `non-trivial`
wording. The parser remains strict about safety outcomes but accepts equivalent
receipt formatting rather than fixed headings.

The first fault-injection attempt exposed a further bypass: denying only the
`reviewer` permission led Core to dispatch `explorer` with a prompt telling it to
act as the reviewer, then claim review success. The policy now requires the named
`reviewer` subagent and explicitly forbids explorer substitution. The final harness
still denies only reviewer, deliberately leaves explorer available, and fails if
any task subagent is used; the new live run proves this bypass is closed for the
smoke task. A separate earlier harness failure also proved that clearing inherited
boolean environment variables must use `Remove-Item Env:...`, matching the
production launchers, rather than writing an empty string.

**Honest limitation.** Static checks prove the required rules are present and not
inverted, and the live fault-injection smoke now proves Core obeys the unavailable-
reviewer rule on one bounded task. That single smoke does not establish general
reliability. The baseline showed the model already had "verify with executed
evidence" and still produced 6/6 incorrect-done claims. Enforcement remains
prompt-level. Phase 3 is still the efficacy test, and its exit criteria are the only
evidence that this remediation worked broadly.

## Phase 3 — Revalidate with frozen tasks

Run a new, pre-registered validation set after Phases 1–2 are green. Use clean
worktrees, held-out checks outside Core, append-only records, and an independent
lead review as in the baseline.

Use a split harness: run normal replay tasks non-interactively with `--auto` so
ordinary permission prompts cannot introduce operator variance, and run
`scripts/smoke-core-reviewer-blocked.ps1` as the separate controlled live negative
path. Its temporary profile explicitly denies reviewer, which `--auto` did not
override in the observed run; explorer stays available so substitution is tested
rather than made impossible. An offline evidence-parser self-test guards the
negative-path verdict against known false-pass forms.

**Required set:**

- C05 replay or an equivalent real performance/cache task (false-green sentinel).
- C08 replay or an equivalent async/concurrency task (review-unavailable sentinel).
- At least four further valid tasks spanning small feature, bug fix, multi-file
  change, and test-failure diagnosis.
- Replace C04 and C07; their frozen issue premises were not reproducible.

**Pre-registered exit criteria:**

- 6/6 strict successes (the existing six-valid-run completion gate).
- 0/6 incorrect completion claims.
- 0 unresolved Important/Critical final-review findings.
- 100% of runs whose deadline-mode file-count and named-risk rules require review
  have a completed reviewer result; any unavailable required reviewer is recorded
  as `verification_blocked`, not a success. Every `review_not_required` receipt has
  per-file classifications and true/false risk flags with affected paths.
- All performance/resource criteria are validated by real-path measurements.
- No test weakening, scope excess, regression, or human rescue.

If any criterion fails, fix the completion/verification policy and repeat this
phase. Do not proceed to routing measurement by averaging away a failure.

## Phase 4 — Reconsider routing only after revalidation

Once Phase 3 passes, begin the already-defined Static Hybrid measurement before
Jev enforcement. Successful GPT-root baseline tasks remain only
`deepseek_replay_candidate`; run DeepSeek-first replays to establish
`cheap-safe` labels. Jev stays shadow-only until the existing minimum of 30
language-stratified real shadow-labelled tasks is reached.

See [Risk-Routed Hybrid Core](2026-09-19-jev-risk-routed-hybrid-core.md) for the
later A/B/C protocol and router safety requirements.

## Execution order

1. ~~Implement Phase 1 and add its failing profile tests first.~~ Done.
2. ~~Implement Phase 2 and add its focused policy tests.~~ Done.
3. ~~Run repository acceptance, pytest, runtime-isolation verification, and a live
   Core smoke that exercises a reviewer-unavailable path.~~ Done. Normal
   non-interactive permissions used `--auto`, while a temporary profile's explicit
   reviewer deny remained authoritative; Core did not substitute explorer, and the
   smoke finished as `verification_blocked` without modifying the deployed profile.
4. ~~Obtain a read-only review of the multi-file policy/test change and resolve
   Important/Critical findings.~~ Done; see the implementation record.
5. Freeze and execute the Phase 3 validation set. **Next.**

No deadline was supplied, so this uses Build discipline rather than a compressed
demo rollout.
