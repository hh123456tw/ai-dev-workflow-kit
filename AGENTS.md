# Single Development Workflow

One workflow. No modes, no multi-agent orchestration. The prompt and the lead
agent definition are the source of truth; this file is the summary.

## Entry surfaces

| Surface | How |
| --- | --- |
| Normal use | Open OpenCode with the stock shortcut. `default_agent` is `stable-lead`, so the session starts as the lead. `/stable <request>` also works. |

Everything resolves to one lead definition: `agents/stable-lead.md`, deployed to
the global agents directory. Model routing comes from `global/opencode.jsonc`.
There is no profile, no launcher wrapper, and no per-machine model file. OpenCode
has no native `profiles/` feature; the retired `profiles/` layout and the
`oc-product` wrapper were removed because they carried the old workflow forward.

## Methodology

Superpowers: brainstorming, planning, TDD, systematic debugging, worktree
isolation, subagent-driven development, verification-before-completion. Matt
Pocock methodology skills are denied in every agent definition and are not
installed by setup.

## Scaling is automatic

The user does not choose a mode. The lead reads the scope and any stated deadline
and applies the matching discipline: Build (over 6 hours), Feature Freeze (2 to 6
hours), or Demo Survival (under 2 hours). With no stated deadline the lead uses
Build discipline and says so. Never invent a deadline.

## Writing rules

- Lead implements directly by default.
- At most one writer at a time.
- Delegate one bounded DeepSeek worker only when all four hold: distinct file
  ownership; no shared route, state, schema, config, or mutable fixture;
  independent acceptance check; independent rollback.
- Never delegate to create the appearance of parallelism.

## Evidence rules

- Progress is judged by artifacts, not status messages.
- No wall-clock reporting requirement is placed on any agent.
- A handback without changed files, exact commands and results, the acceptance
  result, and remaining limitations is rejected.
- No PASS without executed evidence. No self-approval. No faked, weakened, or
  deleted tests.
- Never start new work from a red baseline.

## Model routing

- Lead: the primary model, resolved by each surface's config.
- Bounded workers: DeepSeek V4.1 Flash, pinned in the worker agent definitions.

## Safety

- Never expose or commit credentials; credential paths are denied in every agent.
- Destructive git operations are denied; `git rebase` and `git push` ask first.
- Escalate architecture, auth/payment/security, migration, and test-vs-spec
  conflicts instead of guessing.

## Definition of Done

Acceptance GREEN observed by the lead + relevant regression GREEN +
typecheck/lint GREEN + independent review addressed + the lead's final gate. Only
then merge. After merge, optionally run gstack review, qa, cso, then ship.

## Measurement

Compare process variants by cost per successful slice, never cost per million
tokens. The numbers that matter are wall-clock time, total cost, human
interventions, and one-shot success.
