# Claude Lane Paired Benchmark

**Date:** 2026-09-23
**Status:** Complete. Pre-registered promotion rule **met on point comparison**, but
the quality difference rests on a single task and one run per cell. Workflow: g1 arm
not exposed; g2 re-run exposed 1 of 3 cells with no outcome change (no demonstrated
benefit). No default changes.
**Evidence root:** `C:\Users\cygnu\opencode-benchmarks\claude-lane-ab-20260923\`
(`manifest.json`, `frozen-hashes.json`, `runs/**`, `aggregate.json`, `aggregate.md`,
`progress.log`). Harness generation `claude-lane-ab-g1`, kit commit `1c0bf12`.

## Design

Frozen tasks, requests, and held-out acceptance are the Core baseline's
(`core-baseline-20260920`): C01, C02 (small feature), C03 (bug fix), C05 (multi-file
performance), C06 (multi-file feature), C08 (concurrency bug). Grading follows the
CodeGraph canary, including its fixes: a check printing `NAME=False` at exit 0 fails;
output is redirected through `cmd /c`; hangs are bounded; dropped events are counted.

| Arm | What runs | Cells |
| --- | --- | --- |
| `oc-core` (control, re-run same day) | OpenCode Core, GPT-5.6 lead + DeepSeek reviewer | 6 |
| `claude-core` | Claude Code, Sonnet, kit-core plugin + completion gate | 6 |
| `claude-core-wf` | as `claude-core`, prompt also asks for the Workflow tool | C05, C06, C08 |

Decisions frozen before the first scored run (user): Sonnet; workflow arm only on the
three multi-file/concurrency tasks; control re-run. Order alternated per task.
Promotion rule, pre-registered: `claude-core` strict success >= `oc-core` **and**
claim-based incorrect completion <= `oc-core`; speed and cost are reported, not gating.
S00 smoke runs validated the harness on all three arms and are not scored.

## Results

All 15 cells valid (graded, no timeout, no interruption, no dropped events).

| Task | oc-core | claude-core | claude-core-wf | Failing check (all failing arms) |
| --- | --- | --- | --- | --- |
| C01 | **fail** (298 s) | pass (160 s) | - | `C01_verify.py` (oc-core) |
| C02 | pass (404 s) | pass (1069 s) | - | |
| C03 | pass (257 s) | pass (1389 s) | - | |
| C05 | fail (683 s) | fail (2170 s, turn limit) | fail (2102 s) | `C05_TIMING_UNDER_20PCT=False` |
| C06 | fail (444 s) | fail (711 s) | fail (1015 s) | `C06_corrections_check.py` |
| C08 | pass (768 s) | pass (911 s) | pass (1512 s) | |

| Arm | Strict | Incorrect (legacy) | Incorrect (claim) | Median wall | Median cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| oc-core | 3/6 | 3 | 3 | 424 s | not reported by OpenCode |
| claude-core | 4/6 | 1 | 2 | 990 s | $3.25 (API-equivalent; billed to Max quota) |
| claude-core-wf | 1/3 | 2 | 2 | 1512 s | $3.98 |

- **Promotion rule:** met (4 >= 3; 2 <= 3). The entire quality difference is C01;
  the other five tasks have identical pass/fail across arms. One run per cell is a
  point comparison, not a repeatability claim.
- **Speed:** `claude-core` was slower on 5 of 6 tasks, median 2.3x. It made roughly
  2–3x the tool calls. Part of the gap is the gate's re-runs (below).
- **Tokens:** not compared across providers; OpenCode and Claude Code account input
  and cache differently.

## Findings

1. **The gate caught real false completions, but not hidden-requirement failures.**
   Across 9 Claude runs it blocked 5 substantive false claims (3 skipped required
   reviews, 1 unresolved Important finding, 1 failing command listed as passing),
   all fixed in-run. But in all 4 Claude failures the receipt said `complete`: the
   gate checks the claim against visible evidence, not against the hidden acceptance.
   C05 (a real-path timing criterion) and C06 (review-derived corrections) failed in
   every arm, so they measure the task, not the lane.
2. **Most gate blocks were justified friction.** 51 of 56 block reasons were
   "command never run" or "ran before the latest change". The agent habitually runs
   `cmd 2>&1 | tail -N`, whose exit code is `tail`'s under Git Bash, then lists the
   bare command. The gate is right to refuse that as evidence; the cost is extra turns.
3. **The Workflow arm received no treatment.** The Workflow tool was available in all
   three runs and called zero times. The appended `CORE.md` says parallel work happens
   between worktrees, never inside the session, and outranks the task prompt. This
   arm therefore says nothing about multi-agent orchestration.
4. **C05 `claude-core` hit the 200-turn limit** (201 turns) while the gate was still
   blocking; its `complete` receipt was never accepted. It is counted as a claim under
   the pre-registered definition.

## Workflow re-run (g2, 2026-09-23/24)

**Evidence root:** `C:\Users\cygnu\opencode-benchmarks\claude-lane-wf-20260923\`.
Single-variable change from g1 `claude-core-wf`: an isolated kit copy whose `CORE.md`
permits the Workflow tool for read-only parallel work (exploration, review,
verification) with one writer. Same prompt, model, tools, turn limit, and grading.
A headless probe first confirmed the Workflow tool launches, runs in the background,
and the `-p` session resumes on completion. Pre-registered: a cell with zero Workflow
calls is "not exposed", not a Workflow result.

| Task | oc-core (g1) | claude-core (g1) | claude-core-wf2 | Workflow calls |
| --- | --- | --- | --- | ---: |
| C05 | fail, 683 s | fail, 2170 s, $11.35 (turn limit) | fail, 1586 s, $5.37 | 1 |
| C06 | fail, 444 s | fail, 711 s, $3.03 | fail, 564 s, $1.96 | 0 (not exposed) |
| C08 | pass, 768 s | pass, 911 s, $1.88 | pass, 342 s, $0.67 | 0 (not exposed) |

- **Exposure:** 1 of 3 cells. Even when permitted and prompted, the agent chose the
  Workflow tool only on C05, for one read-only multi-angle review. It did not touch
  the critical path, and C05 still failed the same hidden timing criterion as every
  other arm.
- **No evidence that in-session orchestration helps.** The single exposed cell has
  the same outcome as every arm. Its lower time and cost than g1 `claude-core` cannot
  be attributed to the Workflow tool with one observation.
- **Run-to-run variance is large.** C08 ran on Claude with the same model and
  outcome in 342 s, 911 s, and 1512 s across g1/g2 cells, none of which used the
  Workflow tool. Single-run timing comparisons in this benchmark are dominated by
  noise; only pass/fail is informative at this sample size.
- **Not tested:** DeepSeek as the workflow worker (`claude-ds`), which needs a
  `DEEPSEEK_API_KEY`.

## Next

- Do not switch the default on this evidence alone. Either accept "`claude-core` is
  not worse on quality and is slower", or repeat C01–C08 for both arms to test whether
  the C01 difference holds.
- Orchestration (done in g2): no demonstrated benefit; the agent rarely chooses it.
  For hackathon throughput, parallelism between worktrees (one task each) remains the
  better-founded lever than orchestration inside one task.
- Hidden-requirement misses (C05, C06) are a reviewer/spec problem, not a gate
  problem: test a stronger reviewer (Opus) with an explicit acceptance-criteria pass.
- Reduce pipe friction by stating the no-pipe rule where the agent reads it first,
  and measure whether block counts drop.
