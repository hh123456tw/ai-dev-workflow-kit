# AI Development Modes

Two independent workflows. Prompt is source of truth; details live in each
lead agent's config, not here.

## Stable — `/stable <request>`

GPT-5.6 `stable-lead` + Superpowers + DeepSeek V4.1 Flash. Concurrency = 1, no
Ensemble. For production, portfolio, auth/payment/security, migrations,
complex bugs. Reliability > speed. Matt methodology is disabled in this mode.

## Team — `/team <request>`

`team-lead` + Superpowers + selected gstack skills + conditional OpenCode
Ensemble + DeepSeek V4.1 Flash workers. `team-lead` inherits the active global
model. For hackathons, MVPs, demos, prototypes. Lead-controlled accelerated
delivery: Recon -> Spine -> optional Independent Expansion -> Integration ->
QA -> Demo Hardening. One builder by default; at most two writable workers, and
only after the parallelization rubric passes. No new writable wave before the
prior wave has an integrated green baseline. Parallelize discovery freely;
parallelize code only when ownership is provably independent. Optimize for
time-to-demo, not agent utilization.

## gstack — shared specialist toolbox

Selected skills only, via namespaced commands: `/gstack-qa`,
`/gstack-review`, `/gstack-ship`, `/gstack-cso`, `/gstack-investigate`,
`/gstack-plan-ceo-review`, `/gstack-design-review`, `/gstack-benchmark`.
Never a third methodology; used after verification/integration.

## Model Routing

Thinking, architecture, spec, tickets, integration, final review: GPT-5.6.
Exploration, implementation, tests, mechanical work: DeepSeek V4.1 Flash.

## Escalation Rules

Workers report architecture/spec conflicts, ambiguous criteria, destructive DB
changes, security-sensitive design, and test-vs-spec disagreement to the lead.
They never redefine requirements.

## Definition of Done

Acceptance GREEN observed by the lead + regression GREEN + typecheck/lint
GREEN + independent review PASS. No PASS without executed evidence. No
self-approval. No faked, weakened, or deleted tests.
