# TEAM V2 upgrade prompt

Use this prompt when an existing TEAM profile has drifted or become unstable.

---

Upgrade the existing OpenCode TEAM profile to the stable TEAM V2 architecture. Preserve PRODUCT mode, providers, MCP, credentials, and currently working model routes. Do not reinstall the entire environment.

Core rule:

- GPT-5.6 owns requirement interpretation, architecture, ticket contracts, test seams, critical acceptance tests, diagnosis, and final review.
- DeepSeek V4.1 Flash is a bounded implementation worker only.
- Tests are contracts; the worker cannot modify critical acceptance tests.
- Worker gets at most two attempts. GPT diagnoses between attempt 1 and 2. Two failures trigger GPT takeover.
- Reviewer is a fresh-context GPT agent and reports separate Spec and Standards axes.
- Parallel writers require independent tickets and separate branch + worktree.

Before dispatching a worker, freeze a Ticket Contract containing Goal, Acceptance Criteria, Test Seam, failing test + RED evidence, Allowed Production Scope, Read-only Scope, Forbidden Scope, Verification Commands, and Escalation Conditions.

Worker must escalate instead of expanding scope when it encounters CONTRACT_CONFLICT, ARCHITECTURE_REQUIRED, DEPENDENCY_BLOCKED, ENVIRONMENT_FAILURE, or TEST_INFRA_FAILURE.

Verify the resulting permissions actually prevent the worker from editing tests and launching subagents. Run a disposable smoke test proving RED → bounded implementation → GREEN → fresh review, plus an escalation test.

Do not claim PASS from configuration inspection alone.
