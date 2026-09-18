# Codex Desktop rebuild checklist

> **Historical context.** Earlier revisions of this repository paired Codex
> Desktop with an "OpenCode TEAM V2" workflow and later with a multi-agent
> "Team MVP Sprint". Both are retired. The active workflow is the single
> workflow defined in
> [`docs/superpowers/specs/2026-09-18-single-workflow-design.md`](../../docs/superpowers/specs/2026-09-18-single-workflow-design.md),
> reached through `profiles/product` / `oc-product` or the `/stable` slash
> command.

This repo backs up the **workflow intent**, not account credentials.

The user's historical desktop workflow used Codex Desktop for planning/review and
OpenCode Desktop/TUI for implementation. On a new computer:

1. Install/sign in to Codex Desktop with the intended OpenAI account/workspace.
2. Reconnect any required plugins/apps in Codex Sources / Plugins.
3. Re-authorize provider-backed plugins; OAuth/account grants are not stored in this repo.
4. Open the target project repository.
5. If you use Superpowers in Codex as a separate workflow, install it through the Codex plugin surface available to your account. Keep that separate from the OpenCode single workflow.
6. Keep secrets in account/plugin authorization or local secure storage, never in this Git repo.

## Recommended Codex role alongside this repo

When using Codex Desktop alongside the OpenCode single workflow:

- architecture / plan review
- spec challenge
- final diff / PR review
- difficult fallback implementation when the configured worker model fails

OpenCode (global `/stable` or the `oc-product` profile) remains the execution
environment.
