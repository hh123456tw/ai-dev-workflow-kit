# Risk-Routed Hybrid Core: Jev Research and Architecture Proposal

**Date:** 2026-09-19  
**Status:** Research proposal only; no production implementation approved  
**Baseline:** `docs/superpowers/specs/2026-09-19-three-mode-opencode-workflows-design.md`

## 1. Executive Conclusion

**Jev is worth a Core shadow canary, but not production routing yet.** Its highest potential ROI is one narrow decision made before GPT-5.6 receives a fresh task: whether the task is safe for a DeepSeek fast/guarded execution tier or requires GPT-5.6 expert reasoning. The next-best use is an event-driven stuck detector after DeepSeek failures. Skill routing, context filtering, tool permission approval, and finish gating should not enter v1.

The evidence supports exploration, not deployment:

- TypeSafe provides a real typed API, versioned model, SDKs, probability distributions, confidence, retry controls, and explicit jaggedness documentation.
- Community model routers show meaningful savings on some coding workloads.
- A real 120-session coding benchmark also shows routing can reduce correctness: GPT-5.6 Luna solved a feature 5/5 without routing and 3/5 with routing.
- Jev is early access, its primary language is English, CJK accuracy is lower, and this user has no TypeSafe API key configured.
- OpenCode 1.18.31 has no documented hook that safely changes a model before session metadata is committed. `chat.params` cannot change the model; `chat.message` can potentially mutate the message model but runs after session agent/model bookkeeping. Enforcement needs a separate feasibility spike.

Recommended sequence:

1. **Static Hybrid baseline first.** Establish how much GPT usage deterministic rules alone save.
2. **Jev shadow routing.** Predict and log; do not change execution.
3. **Safe canary only after calibration.** Route only high-confidence easy tasks to DeepSeek; everything uncertain uses existing Core behavior.

## 2. Current Architecture Diagnosis

The current Core benchmark used a fixed two-session topology per task:

```text
GPT-5.6 core-lead implementation
             ↓
DeepSeek read-only reviewer
```

Across nine benchmark runs, Core passed public and hidden tests 9/9. Its primary GPT quota consumption is therefore not review. It is the **root implementation session**: one GPT-5.6 root session for every task, including mechanical feature and bugfix work.

This changes the priority order:

1. Pre-model execution-tier routing can save a GPT root session and has material potential ROI.
2. Stuck detection becomes important only after DeepSeek-first execution is introduced.
3. Review escalation is not a first-order GPT saving because the current Core reviewer is already DeepSeek.
4. Skill routing over six skills has negligible expected ROI.

## 3. Jev: Verified Capabilities and Limits

### 3.1 Official positioning

TypeSafe describes Jev as its first System One model: unstructured textual state plus typed questions in, structured probabilistic decisions out. It does not generate prose or code.

Supported question primitives:

| Primitive | Returns | Core use |
| --- | --- | --- |
| Choice | selected option, probabilities, confidence | route class |
| Score | ordered score, probabilities, confidence | possible risk band, but numeric calibration is weak |
| Noul | probability of yes | atomic risk signals |

Questions sharing one state are evaluated independently and in parallel. This fits a routing pack made of multiple narrow judgments plus deterministic policy code.

### 3.2 Current model and SDK

- Current versioned model: `jev-1.13.0`.
- Aliases: `jev-latest`, `jev-preview`; aliases currently resolve to 1.13.0 but may move.
- Pricing: $0.042 per million input tokens; output is unmetered according to TypeSafe.
- Context: 64k total request budget; 32k for state plus the longest question.
- Input: text only; string, JSON object, or arrays of text.
- Python SDK: `typesafe-sdk` 0.7.0 on PyPI, Python 3.10+.
- API: `POST https://api.typesafe.ai/v1/systemone`.
- API key: `TYPESAFE_API_KEY`; not currently present on this machine.
- SDK default retry policy is two retries with a 30-second total budget. That default is inappropriate for a routing hot path and must be overridden.

### 3.3 Vendor claims versus usable evidence

TypeSafe claims 70–500 ms latency, two orders of magnitude better efficiency, and up to 193.6x faster / 444.6x cheaper on its workflow evals. LangChain repeats an “up to 200x / 400x” characterization. These remain vendor claims for TypeSafe-shaped classification workflows, not evidence for this coding workflow.

The strongest relevant independent evidence is the community `jev-gateway-bench`: 120 real coding-agent sessions with hidden verifiers. GPT-5.6 Sol improved on both tested tasks with routing, but other models became slower and one model lost correctness. That benchmark demonstrates both potential value and non-universality.

### 3.4 Jev 1.13 jaggedness that matters here

Official limitations directly affect this design:

- Literal interpretation: questions and criteria must state exact boundaries.
- Weak numeric reasoning: arithmetic, retry counts, thresholds, dates, and ordering remain code.
- Indirection hurts accuracy: point questions to explicit state fields.
- Irrelevant large state causes context rot: never send the repo or full transcript.
- Adversarial text can move probabilities: Jev is not a security boundary.
- Structural identities are not guaranteed: do not expect probabilities from separately worded questions to sum or negate cleanly.
- CJK is accepted but less accurate than English. This user's Chinese requests require separate calibration.
- Jev can always return an in-schema value, but that value can still be wrong. “No type error” is not “no decision error.”

## 4. External Reference Analysis

All reviewed community repositories were created between 2026-09-16 and 2026-09-19. None has long-term operational evidence.

| Project | Evidence | Useful idea | Limitation / verdict |
| --- | --- | --- | --- |
| LangChain TypeSafe middleware | Official LangChain article/integration; no coding-workflow benchmark in the article | `ModelRouterMiddleware` routes on the latest user request and keeps the selected model for the run; `AutoModeMiddleware` shows a bounded guardrail pattern | Speed/cost figures repeat TypeSafe vendor claims. Useful API/architecture reference, not outcome evidence for this Core. |
| `gargpratyush/jev-router` | 170 stars, 13 forks, tests, Windows/Codex support | One route per fresh user turn; sticky tier for the whole tool loop; low confidence never downgrades; cache-aware no-downgrade; fail-open | No published end-to-end benchmark in README; proxy depends on private CLI request formats. Steal policy ideas, not code wholesale. |
| `0xNatoshi/jev-codex-router` | 237-turn, 7-day local replay claims ~60% list-price savings | Shadow mode, decision log, model/version pin, replay, low-confidence middle-tier fallback | Replay holds token volume constant and does not model prompt-cache invalidation; single-operator data, no hidden task correctness. Useful calibration design, not proof. |
| `vinilana/jev-gateway` + bench | 120 sessions, two coding tasks, five runs per cell, hidden verifier, raw result data | Real on/off benchmark, kill switch, passthrough on low confidence/failure, one Jev call per tool turn | Routing hurt GPT-5.6 Luna correctness on feature work and made some Claude workflows slower. Strong evidence that own-workload benchmark is mandatory. |
| `AbdelStark/bicameral` | v0.1, 4 stars; architecture and offline tests | Deterministic policy owns actions; 900 ms deadline; event-driven Gate/Honest Finish/Stuck; redacted 8k state; observe mode | Tests use `FakeBackend`; live Jev not tested; many advertised later reflexes are explicitly unshipped. Pattern reference only. |
| `Brainwires/jevwire` | v0.4 README reports live API tests and measured 210 ms warm / 501 ms cold judgments | Code-before-model prefilters, pinned model, exact threshold replay, local log, no-side-effect model, 1.5 s hook fail-open | Primarily Claude hook safety/context tooling, not execution-tier routing. Calibration report is behavior telemetry, not labeled accuracy. Good implementation discipline. |
| `BillionsBobby/JevRouter` | 54 stars; tool prediction benchmark | Capability registry, deterministic availability/permission filters, receipts | Benchmark predicts first five tools rather than end-to-end task success. Not enough evidence for model routing. |
| `rizafahmi/pi-jev-task-router` | 0 stars, 23 offline tests | Pre-agent hook; static tier policy; heuristic fallback; explicit thresholds | New demo with no published workload benchmark. Defaults are one machine's model catalog. |
| `rhighs/jev-code` | 5 stars | Constrained AST selection demonstrates Jev's closed-set nature | Attempts to construct code via chained decisions. This conflicts with Jev's official “no generation” guidance and is not relevant to Core. |
| `syndicalt/winnow` | 0 stars, tiny new repository | Row-level relevance scoring | SQL/data filtering experiment, not a coding harness. No evidence relevant to Core. |

### What to steal

- Route once per fresh user turn, then keep the model sticky through the tool loop.
- Static rules and availability checks wrap the model; model probabilities never directly perform actions.
- Fail open to deterministic fallback.
- Pin `jev-1.13.0`; do not use a moving alias for calibrated thresholds.
- Shadow mode, local JSONL decisions, kill switch, and deterministic replay.
- Event-driven stuck checks, not a classifier call after every tool.
- Redact secrets and cap state aggressively.

### What not to steal

- Per-tool routing in v1.
- Tool forcing or direct action execution.
- Full request proxies that depend on unstable private provider protocols.
- Chained Jev decisions as code generation.
- Confidence thresholds copied from unrelated projects.

## 5. Recommended Architecture

```text
                           CORE USER TURN
                                  |
                                  v
                    deterministic static prefilter
                    /            |              \
             obvious fast     uncertain       hard expert
                 |               |                 |
                 |               v                 |
                 |          Jev question pack      |
                 |          (shadow first)         |
                 |               |                 |
                 +------- deterministic policy ----+
                                  |
                 +----------------+----------------+
                 |                |                |
              FAST            GUARDED           EXPERT
           DeepSeek           DeepSeek          GPT-5.6
           standard       + strict verify     hard reasoning
                 |                |                |
                 +----------------+----------------+
                                  |
                         one sticky tool loop
                                  |
                    test / lint / typecheck / smoke
                                  |
                                  v
                         DeepSeek reviewer
                                  |
                   event-driven failure boundary
                           (later stage only)
                                  |
                       static + Jev stuck reflex
                           /              \
                     continue         GPT diagnose
                                          |
                                 minimal handoff only
                                          |
                                  DeepSeek executes fix
```

This remains one active implementation stream. It does not add a fourth mode, scheduler, DAG, swarm, or multiple writable workers.

### Model roles

| Component | Role | Must not do |
| --- | --- | --- |
| DeepSeek V4 Flash | Workhorse: scoped implementation, straightforward feature/bugfix, tests, refactor, UI, plumbing, and execution of a GPT diagnosis | Architecture authority, destructive approval, hidden-test interpretation |
| GPT-5.6 Sol | Scarce expert: architecture, material ambiguity, shared contracts, difficult root cause, high-risk changes, diagnose-only escalation, critical review | Routine CRUD/test/style/plumbing by default |
| Jev 1.13 | Reflex/router: bounded risk classification, uncertainty, later stuck/finish signals | Coding, planning, prose generation, side effects, deterministic verification |

## 6. Routing Taxonomy

### Tier A — Fast

Expected characteristics:

- Explicit, bounded specification.
- Localized ownership.
- Existing deterministic acceptance checks.
- No shared schema/state/public contract/security surface.
- Mechanical implementation, tests, UI styling, mocks, seeds, adapters, local refactor, or reproducible bug.

Execution: DeepSeek V4 Flash, normal verification, DeepSeek reviewer when non-trivial.

### Tier B — Guarded

Expected characteristics:

- Multi-file but clearly specified.
- No hard-risk surface.
- Deterministic acceptance exists.
- Recovery is affordable.

Execution: DeepSeek V4 Flash plus strict acceptance, regression, typecheck/lint/build/smoke, scope check, and mandatory DeepSeek reviewer.

### Tier C — Expert

Triggers include:

- Architecture judgment or materially ambiguous requirements.
- Shared schema/state/public contracts.
- Transactions, concurrency, consistency, auth, security, payments, credentials.
- Destructive or irreversible operations and deployment.
- Unclear root cause or repeated DeepSeek failure.
- Critical demo-path failure where recovery cost is high.

Execution: GPT-5.6 Sol. Deterministic verification remains mandatory.

## 7. Jev Question Pack

Ask all questions over one compact structured state. Use atomic questions; do not ask “which model should handle this?” as one broad judgment.

### Choice

`route_class`:

- `fast`: mechanical, bounded, localized, deterministic acceptance.
- `guarded`: broader but specified, no hard-risk contract, deterministic checks available.
- `expert`: architecture, ambiguity, shared contracts, security, expensive recovery.
- `insufficient_evidence`: state does not support a reliable classification.

### Nouls

1. `mechanically_scoped`: Is the requested work implementable without architecture or product judgment?
2. `requires_architecture`: Does correct implementation require architecture or cross-module contract judgment?
3. `changes_shared_contract`: Does the work change shared schema, state, public API, protocol, or persisted data?
4. `materially_ambiguous`: Could plausible interpretations produce materially different implementations?
5. `failure_recovery_expensive`: Would a wrong implementation be costly or hard to roll back?
6. `deterministic_checks_available`: Are executable acceptance checks sufficient to judge the requested behavior?

Security, credentials, destructive operations, and known risky paths are static hard rules, not model questions.

Noul probabilities and Choice confidence are different measures. Do not apply one shared threshold to both.

## 8. Routing State Contract

### Send

```json
{
  "task": {
    "request": "bounded current user request",
    "language": "zh-TW|en|other",
    "acceptance_summary": ["named executable checks"]
  },
  "repo": {
    "project_type": "python|typescript|...",
    "candidate_paths": ["paths only, no file bodies"],
    "estimated_files": 3,
    "test_commands": ["commands without output"],
    "static_flags": {
      "auth": false,
      "migration": false,
      "shared_contract": false,
      "destructive": false
    }
  }
}
```

### Do not send

- Full source files or repository snapshots.
- Full conversation or tool history.
- Credentials, secrets, `.env`, tokens, keys, or private customer data.
- Raw large diffs or full build logs.
- Hidden tests.
- Data unrelated to the questions.

Target state cap: 4–6k UTF-8 characters. Official guidance and community measurements both show irrelevant/large state harms ranking and accuracy.

Because Jev has lower reported CJK accuracy, Chinese tasks must remain shadow-only until language-stratified calibration exists. Do not add an automatic translation model in v1; that adds cost and another failure source.

## 9. Deterministic Static Layer

**Option B is recommended: static rules first, Jev only for uncertain cases.**

| Option | Assessment |
| --- | --- |
| All tasks → Jev | Wasteful; adds latency/vendor dependency to obvious decisions and sends more data externally. |
| Static rules → uncertain → Jev | Best fit. Obvious fast/hard cases stay deterministic; Jev handles semantic middle cases. |
| Jev first → static override | Safe if overrides are correct, but spends a Jev call even when code already knows the answer. |

Static Expert overrides include actual touched/candidate paths under migrations/auth/security/deployment/payment/transaction/shared-schema areas and explicit destructive intent. Keyword mentions alone are signals, not proof; documentation about auth should not automatically become a security implementation.

Static Fast requires all of:

- Bounded file ownership.
- Explicit acceptance.
- No hard-risk flags.
- No shared contract/persisted-data change.
- Existing executable verification.

Everything else is uncertain and eligible for Jev evaluation.

## 10. Deterministic Policy Pseudocode

Threshold names are placeholders to calibrate; they are not production values.

```python
def route(task_state, static):
    if static.destructive_or_irreversible:
        return EXPERT_GPT

    if static.security_or_credentials:
        return EXPERT_GPT

    if static.migration_or_shared_contract:
        return EXPERT_GPT

    if static.obvious_fast and static.deterministic_checks:
        return FAST_DEEPSEEK

    decision = jev_or_none(task_state, timeout_ms=ROUTER_TIMEOUT)

    if decision is None:
        return static_safe_fallback(static)

    if decision.requires_architecture >= T_ARCH:
        return EXPERT_GPT

    if decision.changes_shared_contract >= T_SHARED:
        return EXPERT_GPT

    if decision.materially_ambiguous >= T_AMBIGUITY:
        return EXPERT_GPT

    if decision.route_class == "fast":
        if (
            decision.choice_confidence >= T_FAST_CONFIDENCE
            and decision.mechanically_scoped >= T_MECHANICAL
            and decision.deterministic_checks_available >= T_CHECKS
        ):
            return FAST_DEEPSEEK

    if static.deterministic_checks and static.recovery_is_affordable:
        return GUARDED_DEEPSEEK

    return EXPERT_GPT
```

Low confidence never routes to Fast. Medium uncertainty may use Guarded only when static checks and recovery are strong. Otherwise fallback is existing Core behavior: GPT-5.6.

## 11. Threshold Calibration

Do not copy 0.5, 0.7, 0.85, or 0.9 from community projects. Their action sets, models, and loss functions differ.

### Labels

A run is **cheap-safe** only when DeepSeek:

- passes public and hidden acceptance;
- needs no GPT rescue;
- introduces no regression;
- receives no Critical/Important final review finding;
- does not modify/disable tests or exceed scope.

### False outcomes

- **False cheap / under-routing:** router selects Fast/Guarded but GPT rescue or hidden-test recovery is required.
- **False expensive / over-routing:** router selects GPT but a controlled DeepSeek replay succeeds without rescue.

False cheap is more expensive because it combines retries, elapsed time, and eventual GPT usage. Optimize an asymmetric loss that penalizes false cheap much more heavily than false expensive.

### Calibration process

1. Collect shadow predictions on at least 30 real tasks, stratified by task type and language.
2. Replay the same repo snapshot through DeepSeek-first where practical to produce outcome labels.
3. Build reliability bins for every Noul and Choice confidence.
4. Pick thresholds to cap false-cheap rate before optimizing GPT savings.
5. Pin thresholds to `jev-1.13.0` plus a question-pack hash.
6. Recalibrate on every model or question-pack change.

Policy-only threshold replay is valid on stored answer distributions. A changed question pack requires new Jev calls; old probabilities are no longer comparable.

## 12. Low-Confidence Policy

```text
high-confidence easy + deterministic checks
→ DeepSeek Fast

medium confidence + no hard risk + strong tests + cheap recovery
→ DeepSeek Guarded

low confidence / conflicting signals / insufficient evidence
→ existing Core GPT-5.6
```

This follows the useful lesson from `jev-codex-router`: always escalating low-confidence cases to the most expensive frontier model can erase savings. In this two-model architecture, Guarded DeepSeek is the middle tier, but static safety conditions must be satisfied first.

## 13. Stuck Detection (Stage 3, Not v1)

Call only at failure boundaries:

- Test/build/typecheck failure.
- Same normalized error signature twice.
- Retry count reaches two.
- Patch reverts or churns the same files/lines.
- New regression after an attempted fix.

Do not call after every tool.

State window:

- Last three failure events.
- Last six mutating/tool summaries.
- Changed files and diff statistics.
- Test pass/fail delta.
- Normalized error signatures.
- Attempts and hypotheses already tried.
- Hard cap around 6k characters; no full logs or source.

Typed output:

- Choice: `progressing`, `retryable`, `oscillating`, `stuck`, `blocked`.
- Nouls: repeated failure, no material progress, environment blocker, root-cause hypothesis changed.

Policy:

```text
progressing → continue
retryable   → allow one retry
oscillating/stuck → GPT diagnose-only escalation
blocked     → environment/user blocker path
```

Bicameral uses a six-turn window and event-triggered reflexes, but it has no live Jev test evidence. Treat the window as a pattern, not a threshold to copy.

## 14. Finish and Review (Defer Enforcement)

Deterministic verification remains authoritative:

```text
tests → lint → typecheck → build → acceptance → smoke
```

Current Core already uses a DeepSeek reviewer. A Jev finish gate cannot reduce much GPT usage today because no GPT review occurs by default. In v1 it would add complexity and another network call without addressing the main quota sink.

Later shadow questions may score:

- scope exceeded;
- test weakened/skipped;
- stub/TODO introduced;
- unexplained workaround;
- risky surface touched;
- acceptance coverage appears incomplete.

If later enforced, static risk and deterministic results still decide whether GPT review is required. Jev only contributes probabilities.

## 15. GPT Escalation Handoff

Default escalation is **diagnose-only**, not full takeover.

```json
{
  "task": "original bounded request",
  "acceptance": ["required checks"],
  "route": "guarded_deepseek",
  "files_touched": ["paths"],
  "diff_stat": {"files": 3, "insertions": 42, "deletions": 10},
  "commands": [{"command": "pytest ...", "exit": 1}],
  "latest_failures": ["normalized concise errors"],
  "attempts": ["what was tried, max two"],
  "current_hypothesis": "bounded hypothesis",
  "static_risk": {"shared_contract": false, "security": false}
}
```

GPT returns root cause, architecture decision if needed, and a constrained fix plan. DeepSeek executes that plan. GPT full takeover is reserved for hard-risk tasks or repeated failure after diagnosis.

Do not transfer the full transcript or force GPT to reread the repository. Attach only selected diff/error snippets when necessary.

## 16. Jev Failure and Fallback Policy

| Failure | Behavior |
| --- | --- |
| API key missing | Static routing; log `jev_unavailable`; existing Core GPT for uncertain cases |
| 401/403 | Disable Jev for the session and surface configuration error |
| Timeout/network/429/5xx | No retry in hot path; static safe fallback; retry on a later user turn |
| Malformed/unknown response | Reject result; static safe fallback |
| Low confidence | Guarded only if static checks support it; otherwise GPT |
| Jev contradicts hard static rule | Hard rule wins |
| Version changes | Keep old thresholds disabled until recalibrated |

Recommended pre-route timeout seed for measurement: 750–900 ms, zero retries. Jevwire measured around 210 ms warm and 501 ms cold, while TypeSafe claims 70–500 ms. The official SDK default 30-second retry budget must not be used here.

Add a circuit breaker after repeated router failures and a kill switch that restores static/existing Core routing instantly.

## 17. Logging and Replay

Log locally in append-only JSONL:

```json
{
  "task_id": "...",
  "timestamp": "...",
  "policy_version": "...",
  "question_pack_hash": "...",
  "jev_model": "jev-1.13.0",
  "language": "zh-TW",
  "static_risk": {},
  "jev_decision": {},
  "confidence": 0.91,
  "predicted_route": "deepseek_guarded",
  "actual_route": "gpt56_current_core",
  "final_models": ["openai/gpt-5.6-sol"],
  "escalated": false,
  "public_pass": true,
  "hidden_pass": true,
  "time_to_green_s": 312,
  "gpt_input_tokens": 0,
  "gpt_output_tokens": 0,
  "jev_latency_ms": 240,
  "fallback_reason": null
}
```

Never log source, secrets, credentials, hidden tests, raw sensitive prompts, or full tool output. Store a redacted replay state or state hash plus approved metadata. Question-pack changes require new predictions; threshold changes can replay old answer distributions exactly.

## 18. OpenCode 1.18.31 Integration Feasibility

Inspection of the installed OpenCode source found:

- `chat.params` runs after model resolution and cannot select another model.
- `chat.message` runs before the user message is saved and may mutate message fields, but session agent/model bookkeeping occurs before the hook.
- The tool loop derives the active model from the user message, so a message-model mutation may work, but session metadata/UI can drift.
- Continuations can switch to `default_agent` unless session and agent are repeated explicitly.

Therefore:

### Stage 0 shadow

A local Core plugin may safely observe `chat.message`, call static/Jev routing, and log a prediction without changing the message model. This is the recommended first integration.

### Stage 1 enforcement

Do not rely on undocumented `chat.message` model mutation without a dedicated spike covering CLI, TUI, Desktop, session resume, compaction, and model/cache metadata.

Safer alternatives to evaluate:

1. External Core launcher/controller that routes a fresh request, then starts OpenCode with an explicit agent/model.
2. A verified local plugin that mutates message model and synchronizes session state through supported client APIs.

For every continuation, explicitly preserve session ID and selected agent/model. Route once per fresh user turn; never reroute every tool call.

## 19. Skill Routing Decision

**Do not build Jev skill routing now.**

Core exposes only six selected skills. Deterministic triggers are sufficient and cheaper. A skill router adds API latency, calibration, logs, and another failure mode without a credible GPT quota saving. Revisit only if the catalog grows to roughly 20–50 skills and real traces show meaningful mis-selection cost.

## 20. Context Filtering Decision

Research only; do not include in v1.

Potentially safe future candidates:

- Duplicate successful tool output.
- Large deterministic build logs after local summarization.
- Search/retrieval candidates after preserving IDs and scores.
- Repeated status/progress chatter.

Never prune:

- User task and acceptance criteria.
- Latest failing test/error trace.
- Current diff and files touched.
- Security/destructive-operation evidence.
- Commands and exit codes used to claim verification.
- Unresolved reviewer findings.

Jev 1.13 itself suffers from irrelevant-state context rot, and jevwire measured ranking degradation when too many candidates shared a request. Context filtering needs a separate benchmark and recovery mechanism.

## 21. Benchmark Protocol

### Variants

- **A — Current Core:** GPT-5.6 direct-first plus DeepSeek reviewer.
- **B — Static Hybrid Core:** static rules; DeepSeek Fast/Guarded; GPT escalation.
- **C — Jev Hybrid Core:** same static rules plus Jev only on uncertain cases.
- **D — Later only:** C plus stuck detector and finish/review shadow gates.

### Tasks

Use 5–10 tasks, at least three repeats per cell after screening:

- Easy: CRUD, styling, localized tests, adapters.
- Medium: cross-file feature, API integration, multi-module change.
- Hard: root-cause debugging, transaction/state issue, architecture/shared contract, material ambiguity.

Every run needs the same snapshot, specification, public tests, hidden acceptance, model versions/settings, timeout, and fresh session. Run one series at a time and delete prior workspaces to prevent cross-run leakage.

### Primary KPI

```text
GPT-5.6 usage per successful task
= (GPT input + output + reasoning tokens, calls, active turns)
  / tasks passing hidden acceptance
```

Secondary metrics:

- public/hidden pass and once-pass rate;
- incorrect-done and regression rate;
- time-to-first-demo and time-to-green;
- retry, stuck, recovery, escalation, and intervention counts;
- DeepSeek/Jev/GPT tokens and costs;
- router latency and failure rate;
- cache-read behavior;
- routing confusion matrix.

### Routing labels

| Predicted | Actual | Meaning |
| --- | --- | --- |
| Cheap | DeepSeek succeeds without rescue | true cheap |
| Cheap | GPT rescue / hidden failure | false cheap / under-route |
| GPT | DeepSeek replay succeeds | false expensive / over-route |
| GPT | GPT genuinely required | true expert |

### Acceptance to enter canary

- Hidden success remains within the predeclared non-inferiority margin versus Current Core.
- GPT usage per successful task drops materially.
- Time-to-green and total cost do not regress beyond predeclared bounds.
- Router timeout/malformed/outage always falls back safely.
- False-cheap rate stays below the calibrated safety target.
- No destructive-action or three-mode isolation regression.

Do not choose numeric margins after seeing results. Pre-register them before the benchmark.

## 22. Rollout Plan

### Stage 0 — Observe

- Current Core still uses GPT.
- Static and Jev predict routes only.
- Collect real, language-tagged routing and outcome data.
- No execution behavior changes.

### Stage 1 — Safe Router Canary

- Static hard rules remain authoritative.
- Only high-confidence, empirically calibrated easy tasks route DeepSeek.
- All other tasks remain existing Core GPT.
- Kill switch and rollback to Current Core.

### Stage 2 — Guarded Tier

- Expand clear medium tasks to DeepSeek with strict deterministic verification and mandatory DeepSeek review.

### Stage 3 — Stuck Reflex

- Add event-driven failure-boundary classification and GPT diagnose-only escalation.

### Stage 4 — Finish/Review Shadow Gate

- Observe whether a risk gate can reduce or target GPT review without correctness loss.

### Stage 5 — Optional Context/Skill Research

- Only after earlier stages show measured ROI.

## 23. Minimal Diff to the Three-Mode Design

Do not rewrite or change mode isolation.

### Amend §5.3 Core

Add:

- Core may optionally run a shadow Risk Router inside Core only.
- Current behavior remains GPT direct-first until canary acceptance.
- Future execution tiers are DeepSeek Fast, DeepSeek Guarded, and GPT Expert.
- Jev never executes side effects.

### Add §5.4 Risk-Routed Hybrid Core

Define:

- static-first routing;
- atomic Jev question pack;
- one route per fresh user turn;
- sticky tool loop;
- DeepSeek/GPT/Jev roles;
- hard-rule precedence;
- minimum-context GPT handoff.

### Amend §7 CLI Entry Points

Clarify that Core routing is internal to `oc-core`; it does not create a fourth mode. Continuations must preserve explicit session, agent, and selected model.

### Add §10.6 Router Verification

Require:

- shadow logs and replay;
- Jev timeout/outage/malformed-response tests;
- static-vs-Jev disagreement tests;
- route stickiness and no agent/model drift;
- language-stratified calibration;
- A/B/C hidden-test benchmark.

### Amend §12 Canary and Rollback

Add Stages 0–4, a Jev kill switch, and Current Core as fallback. Stable remains the process-level rollback.

### Add dependency note

- TypeSafe API is optional and early access.
- Pin `jev-1.13.0` and SDK version.
- `TYPESAFE_API_KEY` remains local and must never enter repo/logs.
- Missing Jev cannot prevent Core from operating.

## 24. Final Recommendation

### Do now

- Keep the approved Three-Mode architecture unchanged.
- Add a research-only shadow-router design to Core.
- Implement deterministic static routing labels and logging first.
- Obtain TypeSafe early-access API credentials before any live Jev calibration.
- Build replay tooling around existing Core benchmark/session data.

### Benchmark first

- Static Hybrid versus Current Core.
- Static + Jev shadow against the same labels.
- Chinese versus English task subsets.
- GPT usage per successful hidden-test pass.
- Router latency and fallback behavior.

### Later

- High-confidence DeepSeek Fast canary.
- Guarded tier.
- Event-driven stuck reflex.
- Finish/review shadow gate.
- Context filtering only after a separate safety benchmark.

### Do not add

- Jev-controlled destructive actions.
- Jev as a coding or architecture model.
- Per-tool rerouting.
- Skill routing for six skills.
- Multi-agent/swarm/DAG orchestration.
- Automatic Vanilla/Stable/Core mode switching.
- Full repo/transcript/source uploads to Jev.
- Production routing before shadow calibration and hidden-test evidence.

## Sources

### Primary

- TypeSafe AI, “Introducing System One Models & Jev,” 2026-09-15: https://typesafe.ai/blog/introducing-system-one-models-and-jev
- TypeSafe documentation index and API/SDK/model pages: https://docs.typesafe.ai/llms.txt
- Jev 1.13 jaggedness: https://docs.typesafe.ai/model-jaggedness/jev-1.13
- LangChain, “Building a Harness with Jev,” 2026-09-17: https://www.langchain.com/blog/building-a-harness-with-jev

### Community references

- https://github.com/gargpratyush/jev-router
- https://github.com/0xNatoshi/jev-codex-router
- https://github.com/vinilana/jev-gateway
- https://github.com/vinilana/jev-gateway-bench
- https://github.com/AbdelStark/bicameral
- https://github.com/Brainwires/jevwire
- https://github.com/BillionsBobby/JevRouter
- https://github.com/rizafahmi/pi-jev-task-router
- https://github.com/rhighs/jev-code
- https://github.com/syndicalt/winnow
