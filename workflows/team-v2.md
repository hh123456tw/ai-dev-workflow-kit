# TEAM V2 — Stable heterogeneous multi-agent workflow

## Roles

### GPT-5.6 Sol orchestrator

Owns:

- requirement clarification
- architecture
- domain model
- vertical slicing
- ticket contracts
- test seams
- critical acceptance tests
- dispatch decisions
- diagnosis between worker attempts

### DeepSeek V4.1 Flash worker

Owns only:

- bounded production implementation
- targeted test execution
- minimal fixes required to make an already-defined contract pass

It does **not** own architecture, scope, acceptance criteria, test seams, or final review.

### GPT-5.6 Sol reviewer

Runs in fresh context and reviews two independent axes:

- Spec: did the change implement the originating contract?
- Standards: is the implementation maintainable and safe?

## Workflow

```text
USER
 ↓
GPT-5.6 orchestrator
 ↓
Matt: grill / domain / codebase design / spec / tickets
 ↓
Ticket Contract
 ├─ goal
 ├─ acceptance criteria
 ├─ test seam
 ├─ failing acceptance test
 ├─ allowed production scope
 └─ forbidden scope
 ↓
Contract freeze + RED confirmed
 ↓
DeepSeek worker (attempt 1)
 ↓
GREEN?
 ├─ yes → fresh GPT reviewer
 └─ no  → GPT diagnosis → DeepSeek attempt 2
                            ↓
                           fail again?
                            └─ yes → GPT takeover
 ↓
Fresh GPT reviewer
 ↓
Spec review + Standards review
 ↓
PASS / CHANGES REQUIRED
```

## Hard stability rules

1. No worker dispatch without a complete ticket contract.
2. GPT chooses the test seam.
3. GPT owns critical acceptance tests.
4. DeepSeek must not modify acceptance tests.
5. DeepSeek gets at most two implementation attempts.
6. Attempt 1 failure is diagnosed by GPT before attempt 2.
7. Two failed attempts cause GPT takeover.
8. Reviewer is fresh-context and read-only by default.
9. Parallel tickets require no dependencies, file overlap, or shared mutable state.
10. Parallel write workers use separate branch + worktree.
