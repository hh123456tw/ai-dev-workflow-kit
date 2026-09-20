# Core Real-Task Baseline Protocol

**Date:** 2026-09-20  
**Status:** Completed; measurement only; operational warning raised (5/6 strict successes)  
**Mode under test:** Current Core (`oc-core`, GPT-5.6 direct-first plus DeepSeek reviewer)  
**Purpose:** Establish a trustworthy baseline before Static Hybrid or Jev shadow routing

## 1. Decision and Scope

Run **eight real backlog tasks** through the current Core workflow. Do not create toy
tasks merely to improve the score, do not enable Jev, and do not change Core policy
during the baseline. Eight tasks fit the requested 5–10 range while giving each of
the four target categories two observations.

This is an operational baseline, not a statistically conclusive model comparison.
Its output is a replayable set of task records and observed distributions for
success, elapsed time, token use, and human intervention.

## 2. Pre-Registered Task Matrix

Before C01 starts, freeze one concrete backlog item into every available slot in a
redacted task manifest. Record each issue or request verbatim; do not replace or
rewrite tasks after seeing how Core performs. If fewer than eight eligible items
exist, freeze a batch of six or seven and retain the empty slots as
`not_available`.

| Slot | Category | Required shape | Exclude |
| --- | --- | --- | --- |
| C01 | Small feature | Local behavior, expected 1–2 production files, executable acceptance | Pure docs/formatting |
| C02 | Small feature | Different subsystem from C01, user-visible or API-visible behavior | Duplicate of C01 |
| C03 | Bug fix | Reproducible incorrect behavior with a known failing example | Environment-only failure |
| C04 | Bug fix | Edge case or regression, different root cause from C03 | Already-known patch |
| C05 | Multi-file change | One feature crossing at least 3 production files with a clear contract | Auth, payment, migration, destructive work |
| C06 | Multi-file change | Refactor or integration crossing at least 2 modules, behavior preserved or specified | Architecture redesign |
| C07 | Test-failure diagnosis | Existing deterministic failing test; root cause not disclosed to Core | Flaky/non-reproducible test |
| C08 | Test-failure diagnosis | Build, typecheck, integration, or regression failure requiring investigation | Missing credentials/access |

If no eligible task exists for a slot, mark it `not_available`; do not substitute
documentation churn or manufacture a defect. A usable first baseline requires at
least six valid tasks and at least one valid task in every category. Prefer all
eight. Store each frozen task ID, category, redacted request hash, starting commit,
and acceptance-manifest hash before the first run. Security, credentials, schema
migration, payment, destructive operations, and architecture decisions remain
Expert-only work and are not baseline canary material.

## 3. Before Each Run

The operator prepares a run card before opening the Core session:

1. Assign `task_id` (`C01` through `C08`) and category.
2. Record repository URL/name, clean starting commit, branch, language, and UTC
   start timestamp.
3. Save the original request exactly as submitted, after redacting secrets and
   customer data.
4. Write acceptance checks before execution:
   - task-specific behavior check;
   - at least one held-out behavior check that Core does not see;
   - regression suite;
   - typecheck/lint/build/smoke where the repository supports them.
5. Keep the held-out check outside Core's worktree/session. Record its hash and
   expected behavior in the operator manifest without exposing its body to Core.
6. Record candidate scope and known risk flags without providing a solution.
7. Record the OpenCode version, exact runtime model identifiers/settings, Core
   config commit/hash, session ID, timeout, and usage-accounting source.
8. Verify the starting branch is clean and the pre-existing suite is green. If it
   is red for an unrelated reason, the run is invalid and must not start.
9. Create a clean isolated branch/worktree from the frozen commit and start a fresh
   `oc-core` session. Do not continue a previous task session. Remove the isolated
   workspace after its evidence is captured so later runs cannot inherit changes.

For C07 and C08, the named failure is expected to be red at the start; unrelated
regression checks must still be green. Preserve the failing command and exact exit
code as baseline evidence.

## 4. During the Run

- Start the timer when the original task is submitted to Core.
- Let Core follow its normal policy. Do not coach it pre-emptively.
- Do not silently repair the patch, alter tests, or add acceptance criteria.
- Log every human message after kickoff as one of:
  - `clarification`: answers a question without changing the requirement;
  - `correction`: redirects an incorrect interpretation or approach;
  - `access`: supplies permission or access Core could not provide itself;
  - `rescue`: gives a diagnosis, patch, command, or implementation direction.
- A repeated message in the same category is another intervention. Pure progress
  observation is not an intervention.
- Log Core escalation to GPT/worker/reviewer separately from human intervention.
- Stop the run when all pre-registered checks first pass, or at 45 minutes. A
  timeout is a valid failed result; do not extend it after seeing progress.

The timer includes model and tool latency. Also record human-wait seconds when the
session is blocked awaiting an answer, so later analysis can report both raw wall
time and `adjusted_time_s = wall_time_s - human_wait_s`.

## 5. Outcome Definitions

### Success

A run is successful only when all conditions hold:

1. Task-specific acceptance passes.
2. Held-out acceptance passes.
3. Regression checks pass.
4. Required typecheck/lint/build/smoke checks pass.
5. No existing test was weakened, skipped, or deleted to obtain green.
6. No unresolved Critical or Important final-review finding remains. Record
   `review_not_required` when Core policy does not require a reviewer; do not
   pretend that an unperformed review passed.
7. The implementation stays within the requested scope.
8. No human `rescue` supplied the substantive solution.

`success_after_rescue` is tracked separately and does **not** count as baseline
success. An invalid run (dirty/red starting state, infrastructure outage, accidental
secret exposure, or changed specification) is excluded and rerun with a new run ID
such as `C03-R2`; never overwrite the original record.

### First-pass success

`first_pass_success=true` only if Core reaches the final green result without a
failed completion claim, corrective intervention, rescue, or second implementation
attempt after deterministic verification fails. Routine TDD red-to-green cycles do
not count as failed attempts.

### Incorrect done

Set `incorrect_done=true` whenever Core claims completion before a required check
passes or before an Important/Critical defect is resolved, even if it later repairs
the task.

## 6. Metrics

### Primary

- **Strict success rate:** successful valid runs / valid runs.
- **First-pass success rate:** first-pass successful valid runs / valid runs.
- **Median time-to-green:** median `wall_time_s` among successful runs.
- **Median model tokens per successful task:** input, output, and reasoning tokens
  reported separately by model. Report a total only when the provider supplies a
  directly comparable total; never construct a partial total around `null` fields.
- **Human intervention:** total and median interventions per valid run, with
  correction and rescue counts reported separately.

### Secondary

- Success by category and language, plus invalid-run count and reasons.
- Adjusted time-to-green, timeout rate, incorrect-done rate, regression rate.
- GPT and DeepSeek calls, active turns, reviewer findings, retry count.
- Cache-read/cache-write tokens and provider cost when actually reported.
- Files changed, insertions, deletions, and scope-exceeded flag.

Never estimate missing token or cost fields. Store `null` plus the collection source
(`session_stats`, `provider_usage`, or `unavailable`). Keep input, output, reasoning,
cache-read, and cache-write fields separate; do not compare totals built from
different accounting definitions.

For this eight-task baseline, report counts, rates, median, and range. Do not use a
single average or a pseudo-precise p95 as the headline.

## 7. Run Record

Store one append-only JSONL object per attempt outside the repository. Recommended
local path: `~/opencode-benchmarks/core-baseline-20260920/runs.jsonl`.

```json
{
  "schema_version": 1,
  "run_id": "C01-R1",
  "task_id": "C01",
  "category": "small_feature",
  "language": "zh-TW",
  "repo": "redacted-name-or-public-url",
  "start_commit": "0123456789abcdef",
  "branch": "benchmark/C01",
  "opencode_version": "1.18.31",
  "core_config_hash": "sha256-of-effective-config",
  "session_id": "redacted-or-local-session-id",
  "request_sha256": "hash-of-redacted-verbatim-request",
  "acceptance_manifest_sha256": "hash-of-public-and-held-out-manifest",
  "started_at": "2026-09-20T00:00:00Z",
  "finished_at": "2026-09-20T00:06:12Z",
  "wall_time_s": 372,
  "human_wait_s": 20,
  "adjusted_time_s": 352,
  "timeout": false,
  "acceptance_commands": [
    {"command": "pytest tests/test_feature.py -q", "exit_code": 0},
    {"command": "<redacted held-out verifier>", "exit_code": 0},
    {"command": "pytest -q", "exit_code": 0}
  ],
  "strict_success": true,
  "downstream_label": "deepseek_replay_candidate",
  "success_after_rescue": false,
  "first_pass_success": true,
  "incorrect_done": false,
  "regression": false,
  "scope_exceeded": false,
  "review_findings": {"critical": 0, "important": 0, "minor": 1},
  "review_status": "performed",
  "interventions": {
    "clarification": 0,
    "correction": 0,
    "access": 0,
    "rescue": 0,
    "human_minutes": 0
  },
  "implementation_attempts": 1,
  "models": {
    "openai/gpt-5.6-sol": {
      "settings_hash": "sha256-of-effective-model-settings",
      "calls": 1,
      "input_tokens": 12000,
      "output_tokens": 2100,
      "reasoning_tokens": null,
      "cache_read_tokens": null,
      "cache_write_tokens": null,
      "cost_usd": null
    },
    "deepseek/deepseek-v4-flash": {
      "settings_hash": "sha256-of-effective-model-settings",
      "calls": 1,
      "input_tokens": 4200,
      "output_tokens": 450,
      "reasoning_tokens": null,
      "cache_read_tokens": null,
      "cache_write_tokens": null,
      "cost_usd": 0.0012
    }
  },
  "usage_source": "session_stats",
  "changed_files": 2,
  "insertions": 48,
  "deletions": 7,
  "notes": "No requirement changes"
}
```

Alongside JSONL, retain the redacted original request, hashed acceptance manifest,
sanitized model-settings snapshot matching each `settings_hash`, sanitized diff
summary, concise command/exit-code summaries, and sanitized exported session usage
under the run ID. Apply the same redaction policy to every free-text field,
including `notes`, commands, diffs, and tool output. Do not copy raw private source
or full logs into the benchmark directory; leave them under the repository or
session store's existing access controls. Never store credentials, `.env` files,
hidden-test bodies, customer data, or raw sensitive prompts. Only sanitized
aggregate results belong in git.

## 8. Operator Summary Table

Maintain this compact table while the full evidence remains in JSONL:

| ID | Category | Success | First pass | Wall | Tokens | Interventions | Rescue | Notes |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| C01 | Small feature | yes | no | 325s | 64232/7467/1927 | 1 | 0 | `guaardvark#199`; first completion missed a settle step and skipped the dependency-complete suite; one correction fixed both |
| C02 | Small feature | yes | no | 799s | 65984/9607/2897 | 1 | 0 | `pwned-deps#6`; first completion green on all gates, but Core dispatched no reviewer despite the multi-file policy, so the lead reviewed; one Important finding fixed by one correction; 2 Minor findings open |
| C03 | Bug fix | yes | no | 616s | 48652/6631/3069 | 1 | 0 | `agentcost#122`; Core ran its own reviewer and fixed its 2 findings in-run, but the lead's reviewer found a further Important classification defect (ancestor agent name beat the leaf) fixed by one correction; issue's stated mechanism was wrong (Hermes discovery found nothing at all) |
| C04 | Bug fix | n/a | n/a | n/a | n/a | 0 | 0 | `agentcost#121` **not_available**: the stated 6-dp drift does not reproduce (measured 7e-14 at 500 calls, 6.8e-12 at 10k, 6.2e-10 at 400k; round-6 equal in every case). The only failing criterion is exact Decimal match, which contradicts the 6-dp criterion. Escalated; not run. |
| C05 | Multi-file | **no** | no | 1094s | 70810/13686/6730 | 1 | 0 | `agentcost#125`; cache works (criteria 2/3/4 pass) but criterion 1 fails: measured warm/cold = 0.335 (needs <0.20). `--no-cache` 0.92s vs cold 2.05s vs warm 0.69s, so the cache write makes the first run 2.2x slower than no cache. Core's in-suite check used a synthetic counter = false green |
| C06 | Multi-file | yes | no | 1540s | 177216/15596/6423 | 1 | 0 | `agentcost#130`; all 6 criteria pass, but the lead reviewer found 4 Important findings the in-run review missed (one broken plugin broke built-in `--parser` selection; no project-over-user precedence; non-numeric plugin output reached cost arithmetic; `analyze <dir> --agent` loaded every plugin). One correction fixed all 4 plus a 5th Core found itself |
| C07 | Test diagnosis | n/a | n/a | n/a | n/a | 0 | 0 | `agentcost#128` **not_available**: no `datetime.utcnow()` exists anywhere in the repo (never has, per `git log -S`), and `pytest -W error::DeprecationWarning` already passes 121 tests at baseline. Escalated; not run. |
| C08 | Test diagnosis | yes | no | 830s | 81433/6938/4587 | 1 | 0 | `pi-agent-python-sdk#36`; 5 failing burst tests went green, but Core's own reviewer dispatch was permission-rejected so the change shipped unreviewed; the lead reviewer found a **Critical** that turned a benign race into a permanent event-loop hang, fixed by one correction and re-verified up to n=20000 |

## 9. Baseline Completion Gate

The dataset is complete enough for the next decision when:

- 6–8 valid real tasks are recorded, with every category represented;
- all acceptance criteria and intervention labels were written without retroactive
  score changes;
- every success has executable green evidence and a final review where Core policy
  requires one;
- every run has elapsed time and intervention counts;
- token fields have either measured values and source or explicit `null` values;
- failures and invalid attempts remain in the append-only record;
- a sanitized aggregate summary includes invalid attempts and has been reviewed for
  arithmetic and labeling.

Do not impose a speed or token pass threshold on the baseline itself: these runs
define those reference values. For eight valid tasks, a provisional operational
warning is raised below 7/8 strict success. For six or seven valid tasks, raise it
below 87.5% strict success, evaluated as an exact count (`ceil(0.875 * valid_runs)`).
Also raise a warning if any category has no successful run, any Critical finding
remains, or more than 25% of valid tasks require human rescue. Investigate those
failures before adding routing complexity.

## 10. How This Feeds the Jev Experiment

After the baseline:

1. Mark successful Current Core tasks only as `deepseek_replay_candidate`; Current
   Core uses GPT-5.6 as the root implementer and therefore cannot establish the
   Jev proposal's DeepSeek-specific `cheap-safe` label.
2. Label a candidate `cheap-safe` only after a controlled DeepSeek-first replay
   passes public and held-out acceptance without GPT rescue, regression,
   Important/Critical findings, test weakening, or scope excess.
3. Preserve the starting commit, request hash, acceptance manifest, exact model
   identifiers/settings, and result so
   Static Hybrid and later Jev shadow decisions can be evaluated against the same
   cases.
4. This real-work baseline intentionally uses one observation per distinct task.
   The later controlled A/B/C benchmark must perform at least three repeats per
   task/variant cell from isolated copies of the same snapshot.
5. Run Static Hybrid measurement before Jev enforcement.
6. Obtain TypeSafe credentials only for Jev shadow calls; missing credentials must
   never block Core.
7. Keep Chinese and English results separated because Jev's documented CJK
   performance is lower.
8. Do not enable automatic routing from this 6–8 task baseline. The Jev proposal
   still requires at least 30 real shadow-labeled tasks before threshold
   calibration.

The immediate deliverable is therefore a measured Current Core baseline, not a
router and not an API integration.
