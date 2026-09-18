# Single Workflow Design

**Date:** 2026-09-18
**Status:** Approved design; supersedes the two-mode STABLE/TEAM design
**Audience:** Solo developer doing production work and time-boxed hackathon MVP work

## 1. Problem

The repository previously offered two workflows: `/stable` and `/team`. `/team`
carried its own methodology, its own agents, and an optional OpenCode Ensemble
multi-agent execution layer.

Observed in practice, `/team` was slower, more token-expensive, and less reliable
than `/stable`. The decisive cost is structural rather than a tuning problem:

- Ensemble injects live team state (member status, task counts) into the lead's
  system prompt on every model call. Prompt caching depends on a byte-stable
  prefix, so that prefix changes whenever any teammate changes state. Cache reuse
  collapses on the lead's session.
- Every teammate is an independent session with its own cold context. N agents
  means N uncached prefixes and N re-readings of the same repository.

A second workflow also duplicated maintenance: two lead definitions, two
methodologies, two sets of agents, two launch surfaces, and two test suites for
what is, in daily use, one job.

## 2. Decision

Keep exactly **one workflow**. Do not maintain a separate multi-agent mode.

```text
GPT-5.6 + Superpowers  (the single rule set)
        |
        +-- lead scales process automatically to scope and deadline
        +-- lead implements directly by default
        +-- delegate one bounded DeepSeek subagent when a slice is
            self-contained and delegation clearly pays
```

The workflow is a single rule set with automatic scaling, not a mode switch. The
user never chooses between "stable" and "fast"; the lead reads scope and the
user-stated deadline and applies the appropriate discipline.

## 3. Removed

- The OpenCode Ensemble plugin and every dependency on it.
- The `/team` command and the `team-lead` primary agent.
- The `profiles/team` Desktop/CLI profile and the `oc-team` launcher.
- Team-specific global subagents (`team-scout`, `team-builder`, `team-reviewer`).
- The Team acceptance suite.
- Any parallel-writer orchestration policy, worktree fan-out, shared task board,
  and teammate messaging.

Rationale for removing rather than gating: a cache-hostile execution layer that
must be avoided to stay affordable is a liability, not a capability. Removing it
also removes the maintenance surface that produced the instability.

## 4. Retained

- **`/stable`** and **`stable-lead`** as the global entry point.
- **`profiles/product`** and **`oc-product`** as the independently launchable
  Desktop and CLI entry surface.
- **Superpowers** as the development methodology in both surfaces.
- **gstack** as the shared specialist toolbox, used after integration.
- **DeepSeek V4.1 Flash** as the optional bounded implementation worker.
- The existing safety rules: no credential exposure, no silent destructive git
  operations, no self-approval, no faked or weakened tests.

## 5. Folded In From the Team Design

These policies were the genuinely valuable part of the Team work. They become
built-in behaviour of the single workflow rather than a separate mode.

### 5.1 Scope before build

The lead defines the smallest demo-able outcome and its acceptance check before
writing code. Excluded scope is stated, not implied.

### 5.2 Spine before breadth

One vertical end-to-end path is completed and verified before broadening. A
scaffold or a wide horizontal layer that cannot yet be demonstrated is not
progress.

### 5.3 Delegation is conditional, not automatic

The lead implements directly by default. It delegates one bounded subagent only
when all of the following hold:

1. the slice has a distinct, explicitly listed file ownership boundary;
2. it shares no route, shared state, schema, package or deployment
   configuration, or mutable test fixture with concurrent work;
3. it has an independent acceptance check;
4. its result can be reverted independently.

If any condition is false, the lead does the work. Delegation is never used to
create the appearance of parallelism.

### 5.4 At most one concurrent writer

There is no parallel-writer fan-out. If two slices are genuinely independent,
they are still executed sequentially unless the user explicitly asks otherwise,
because the measured cost of coordination exceeded the measured benefit.

### 5.5 Deadline-aware discipline

When the user states a deadline or remaining time, the lead selects a phase:

| Phase | Remaining time | Allowed work |
| --- | --- | --- |
| Build | more than 6 hours | Build the spine and high-value features normally. |
| Feature Freeze | 2 to 6 hours | Finish accepted work, integrate, verify; reject scope expansion. |
| Demo Survival | less than 2 hours | Only demo blockers, crashes, broken UX, seed or mock fallbacks, and presentation-path work. |

During Demo Survival, refactors, dependency upgrades, architectural cleanup, and
schema migrations are prohibited unless they are the direct blocker to the
declared demo path.

The lead never invents a deadline. Without a stated deadline it uses Build
discipline and says so.

### 5.6 Artifact-based progress

Progress is judged by artifacts, not by status messages. No wall-clock reporting
requirement is placed on any agent, because agents do not reliably track time and
such prompts encourage status-only output.

A delegated slice is complete only when the handback contains:

- changed files;
- commands run with their exact result;
- the acceptance-check result;
- any remaining limitation or blocker.

### 5.7 Integration before the next slice

No new work starts from a red baseline. The lead runs the build, the relevant
tests, and a smoke check of the affected path before starting the next slice.

### 5.8 Measurement

When comparing process variants, measure cost per successful slice, never cost
per million tokens. The relevant numbers are wall-clock time, total cost, human
interventions, and one-shot success.

## 6. Roles and Model Routing

| Role | Responsibility |
| --- | --- |
| Lead (GPT-5.6, primary model) | Scope, architecture, delegation decision, implementation by default, integration, verification, final review |
| Bounded worker (DeepSeek V4.1 Flash, optional) | A self-contained slice with declared file ownership and an evidence-based handback |

Model routing is configuration, not prompt text. Agent Markdown files carry no
`model:` line; the profile resolves routing through the supported config key.

Verified behaviour of OpenCode 1.18.31, which this design depends on:

- the supported config key is singular `agent`, not `agents`;
- `agent.<name>.model` accepts `{env:VAR}` interpolation;
- an explicit `model:` in agent Markdown overrides the config value, so agent
  files must omit it;
- config `agent.<name>.model` overrides an inherited or globally merged model,
  which makes routing deterministic per profile.

## 7. Entry Surfaces

| Surface | Command or profile |
| --- | --- |
| Global slash command | `/stable <request>` |
| Desktop profile | `profiles/product` |
| CLI launcher | `oc-product` |

One workflow, three ways to start it. There is no second lane to keep in sync.

## 8. Quality Gates

Per slice, the lead confirms:

1. the relevant formatter, lint, typecheck, and tests pass, with executed
   evidence;
2. an independent read-only review of the change where the change warrants it;
3. a smoke check of the affected user path when the application is runnable.

Before declaring a demo or release ready, the lead confirms:

1. a fresh start works;
2. the core journey completes end to end;
3. external failures produce an understandable state or a deliberate fallback;
4. no obvious console errors or broken UI on the demo path;
5. seed data, credentials, and a short demo script are ready.

## 9. Acceptance Criteria

1. Exactly one workflow is documented and launchable.
2. No Ensemble dependency remains in any active configuration or script.
3. No `/team`, `oc-team`, `profiles/team`, or Team-specific agent remains.
4. `/stable`, `stable-lead`, `profiles/product`, and `oc-product` continue to work.
5. Superpowers and gstack remain available in the retained lane.
6. Agent Markdown files contain no `model:` line; routing is resolved by profile
   config.
7. Delegation conditions and the single-writer rule are stated in the lead
   definition.
8. Deadline phases and the Demo Survival prohibitions are stated in the lead
   definition.
9. The acceptance suites pass with no reference to the removed workflow.
10. Credential and destructive-git protections are preserved.

## 10. Rollback

If the single workflow proves insufficient for a genuinely parallel workload,
the correct response is to re-evaluate with measured evidence, not to restore the
removed orchestration by default. Any future parallelism must demonstrate a
wall-clock or cost-per-successful-slice win over the single workflow before it is
adopted. Git history preserves the removed design if it is ever needed for
reference.
