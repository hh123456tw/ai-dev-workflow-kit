# Stable mode

Stable is one of three isolated modes (Vanilla, Stable, Core). It keeps the full
Superpowers plugin and the cost-control lead; this document describes only the
Stable workflow.

## Stack

- Primary model: GPT-5.6 Sol (lead / planner / implementer / reviewer; the actual provider/model ID is supplied locally)
- Worker model: DeepSeek V4.1 Flash (bounded implementation slices)
- gstack: product, planning, review, QA, security, and release workflows
- Superpowers: implementation discipline, TDD, debugging, worktrees, verification

## Flow

```text
Need / idea
   ↓
Scope: smallest demo-able outcome + acceptance check + explicit exclusions
   ↓
Superpowers engineering discipline (brainstorm → plan → TDD)
   ↓
Delegation check: four conditions; if any fails, the lead implements directly
   ↓
Bounded DeepSeek worker (only when the slice is provably independent)
   ↓
Independent read-only review + lead's final verification
   ↓
gstack QA / ship
```

## Rules

1. Stable is one of three modes (Vanilla, Stable, Core). Within Stable the user does not choose a mode; the lead scales process to scope and deadline.
2. At most one writer is active at a time.
3. Delegate only when all four conditions hold: distinct file ownership; no shared route, state, schema, config, or mutable fixture; independent acceptance check; independent rollback.
4. Progress is judged by artifacts, not status messages. No wall-clock reporting requirements.
5. Never start new work from a red baseline.
6. Retired methodology skills are denied in every agent definition and are not installed by setup.
7. Provider secrets remain outside this repository.
8. Measure cost per successful slice, never cost per million tokens.
