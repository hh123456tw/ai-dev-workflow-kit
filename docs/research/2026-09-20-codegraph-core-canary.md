# CodeGraph-only Core Canary

**Status:** Benchmark complete. Promotion rule **not met**; verdict **inconclusive/underpowered** with an unfavourable input-token direction. `oc-core` remains the default; CodeGraph is not promoted. The treatment config and launcher were removed as required by the frozen rule.
**Pinned release:** CodeGraph `0.20.1`, Windows x64.  
**Control:** `oc-core`.  
**Treatment:** `oc-core-codegraph` with upstream `--profile=core` (8 tools).

## Isolation

This is a CodeGraph-only treatment. The normal `oc-core` config has no MCP entry.
The treatment uses the same model, `core-lead`, workers, skills, permissions, task
prompt, and acceptance checks. Do not add persistent memory, design intelligence,
Jev, model routing, or another MCP during this canary.

The first tools of interest are `get_edit_context`, `get_ai_context`, and
`symbol_search`. Record which CodeGraph tools were actually called; availability
alone is not treatment exposure.

## Historical install and launch

The following commands describe the treatment used during the canary. The
`oc-core-codegraph` launcher is no longer shipped after the no-promotion decision.

```powershell
pwsh -NoProfile -File scripts/install-codegraph-windows.ps1
pwsh -NoProfile -File scripts/setup-windows.ps1
oc-core                 # control
oc-core-codegraph       # treatment
```

The installer pins both the server and adjacent `onnxruntime.dll`, verifies each
official `.sha256` sidecar against repository-pinned hashes, and checks the binary's
reported version. During the canary, the treatment launcher rechecked both the
executable and `onnxruntime.dll` hashes on every run.

## Paired A/B manifest

- Use at least 6 valid tasks, each run once in control and once in treatment.
- Freeze task prompt, repository revision, hidden acceptance, deadline mode, and
  operator intervention policy before the first run.
- Alternate order by pair (`AB`, `BA`, `AB`, `BA`, ...) to reduce warm-cache and
  learning bias. Use clean sessions and worktrees; never continue across arms.
- Pre-index treatment before timing and report that indexing cost separately. Also
  retain one cold-index measurement as an operational startup metric.
- Primary safety gate: treatment strict success and incorrect-completion rate must
  be no worse than control. Any regression stops adoption.
- Primary efficiency metric: paired change in input tokens.
- Secondary metrics: output tokens, wall time, model cost, first-pass acceptance,
  tool-call count, CodeGraph-tool utilization, and human correction/rescue.
- Report medians and every pair; do not hide a failed task in an average.

## Promotion rule

Keep `oc-core` as the default. Promote CodeGraph into normal Core only in a separate
decision after all safety gates pass and the treatment shows a repeatable input-token
or wall-time benefit on at least 4 of 6 pairs. Otherwise remove the treatment config
and launcher; the control remains unchanged.

## Installation and smoke evidence

- Server SHA-256: `aa1b6108217c119af6ac444b8652a0eadcfe2c343bff78ead2edd15b6b7b15b1`.
- `onnxruntime.dll` SHA-256: `52f8ebe8f08f369a44fed6d1cb680c7c89169795e1c2949ee25b88b538ef0948`.
- `codegraph-server --version` returned `codegraph-server 0.20.1`.
- `oc-core-codegraph mcp list` reported one connected server with
  `--mcp --profile=core`; `oc-core mcp list` reported no MCP servers.
- Read-only treatment session `ses_f40aaf0d0ffeFhTNxA647WLik1` called
  `codegraph_codegraph_symbol_search` and found `ThreeModeBundleTest` at
  `tests/test_profile_bundle.py:108`. The server reported that embeddings were still
  building and correctly fell back to name/text search.
- That smoke's first step used 9,479 input tokens and its cached final step used 344
  input tokens. This is startup evidence, not an efficiency result; only the paired
  protocol above can establish benefit.

## Paired A/B results (2026-09-21)

Evidence root: `C:\Users\cygnu\opencode-benchmarks\codegraph-canary-20260920\`
(`manifest.json`, `runs/**`, `aggregate.json`, `aggregate.md`, `crosscheck.json`).
Workflow commit `e1f26e08a07e6a3236ff929827384c49765993f9`. All 12 arms started in the
frozen order; each arm started with a detached worktree and fresh session, using
the same prompt and public and held-out acceptance. Three treatment arms were
later continued after infrastructure interruptions and are excluded as intervened.

**Verdict: do not promote. The result is inconclusive, not a clean negative.**

Only 2 of 6 pairs were usable against the frozen usability rules, so the
"4 of 6 pairs" speed rule is not evaluable. Unusable pairs and why:

| Pair | Blocker |
| --- | --- |
| C01 | control metrics not reproducible (1 dropped JSONL event); treatment exhausted the outer command budget after 1497.536 s of pre-indexing, then continued |
| C02 | treatment interrupted by API 429 then continued; treatment launcher did not exit (MCP descendant held the stdout handle) |
| C03 | mixed harness generation (control ran the legacy pipeline harness, treatment the cmd-redirect harness) |
| C08 | treatment interrupted by API 429 then continued |

- Usable pairs only: strict success control/treatment `0/0`, incorrect completion
  `2/2`, improved input tokens `[]`, improved wall time `[C06]`, promotion `false`.
- All-pairs intent-to-treat sensitivity check: strict success `3/2`, incorrect
  completion `3/4`, improved either metric `[C01, C03, C06]` (3 of 6, below the
  required 4), promotion `false`.
- Input tokens were higher under treatment in **6 of 6** pairs (C01 69,578→135,410;
  C02 90,538→129,304; C03 39,834→52,196; C05 99,530→161,995; C06 71,379→74,730;
  C08 61,162→228,776). This is the strongest directional signal and it runs against
  the treatment, but with one run per arm it is not a repeatability claim.
- Three operator interventions occurred, all in treatment arms: C02 and C08 were
  interrupted by provider HTTP 429 `usage limit reached`; C01 exhausted the outer
  command budget because pre-indexing consumed 1497.536 seconds.

### Instrument defects found and fixed during the canary

These are why the run is reported as inconclusive rather than as a clean loss, and
they must be fixed before any further canary:

1. `verify-one.ps1` originally graded exit codes only. The frozen
   `C05_timing.py` prints `C05_TIMING_UNDER_20PCT=False` and exits `0`, so C05 was
   first recorded as a strict pass in both arms. Acceptance grading now also fails
   a check that prints a `NAME=False`/`NAME=FAIL` marker.
2. Wall time was first measured through a PowerShell pipeline, which waits on any
   descendant that inherits the stdout handle. A CodeGraph MCP child kept the
   pipeline open after the model had finished, inflating C02-treatment from
   ~654 s of model-active time to 2867 s. The harness now redirects to files via a
   `cmd /c` wrapper, records `model_active_time_s` separately from
   `launcher_overhead_s`, and guards `WaitForExit` with a timeout.
3. Resumed runs were initially counted as clean. Runs are now flagged `intervened`
   when a recovery block, `resume-record.json`, or `interrupted.json` exists.
4. Token and tool totals are now re-derived from the persistent session store by
   `crosscheck.py`; 11 of 12 runs reproduce exactly. `C01-control-R2` loses one
   `tool_use` event to a 35 KB malformed JSONL line that the old harness silently
   dropped, so `run-one.ps1` now counts and records `dropped_events`.
5. Harness generations were mixed mid-canary (C01/C02/C03-control on the legacy
   pipeline harness, later arms on the cmd-redirect harness). Mixed-generation
   pairs are now blocked from pairing rather than silently compared.

### Consequences for the next canary

- Freeze one harness generation before the first arm and do not change it mid-run.
- Budget for provider quota: two arms were interrupted by HTTP 429. Interrupted
  arms are not valid measurements and must be re-run as fresh attempts.
- Run each arm more than once if the promotion rule is to require a *repeatable*
  benefit; a single run per arm cannot establish repeatability.
- Keep the treatment launcher from outliving the model, and keep measuring
  model-active time rather than process lifetime.
