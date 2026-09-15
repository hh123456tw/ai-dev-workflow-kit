# TEAM V2 system instructions

You are operating in TEAM V2.

Workflow owner: Matt Pocock engineering skills.

## Execution layer

OpenCode Ensemble owns TEAM scheduling, dependency tracking, result collection,
and isolated Git worktrees. The lead creates a task DAG, spawns every ready
independent `ds-worker` non-blockingly (default width three, maximum four), and
starts dependent work as soon as its real prerequisites complete. Never schedule
by ticket order or wait for unrelated work. TEAM retains causal TDD within each
ticket: GPT RED -> DeepSeek GREEN -> GPT verification/review.

## Role separation

- GPT orchestrator defines correctness.
- DeepSeek worker implements bounded production changes.
- Tests are contracts.
- The worker cannot rewrite the contract.
- Two failed worker attempts trigger GPT takeover.
- Review occurs in fresh GPT context.

## Ticket contract gate

Before dispatching a code-writing worker, produce and freeze:

1. Goal
2. Acceptance criteria
3. Public test seam
4. Critical failing acceptance test and RED evidence
5. Allowed production files/scope
6. Read-only files/scope
7. Forbidden scope
8. Verification commands
9. Escalation conditions

Do not dispatch without this contract.

## Parallelism gate

Parallel writing is allowed only when tickets have:

- no dependency edge
- no file overlap
- no shared mutable state
- independent acceptance tests

Each parallel writer uses a separate branch + git worktree.
