# AI Development Modes

Two independent workflows. Prompt is source of truth; details live in each
lead agent's config, not here.

## Stable — `/stable <request>`

GPT-5.6 `stable-lead` + Superpowers + DeepSeek V4.1 Flash. Concurrency = 1, no
Ensemble. For production, portfolio, auth/payment/security, migrations,
complex bugs. Reliability > speed. Matt methodology is disabled in this mode.

## Team — `/team <request>`

GPT-5.6 `team-lead` + Matt Pocock skills + OpenCode Ensemble + DeepSeek V4.1
Flash workers. Concurrency = 2-3 (4 only if fully independent). For
hackathons, MVPs, demos, prototypes. Dependency-driven scheduling: spawn every
safe ready ticket at once, unblock dependents as results arrive. One ticket =
one branch = one worktree. Superpowers is disabled in this mode.

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
