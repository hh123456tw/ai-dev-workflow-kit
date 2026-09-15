# Codex Desktop rebuild checklist

This repo backs up the **workflow intent**, not account credentials.

The user's historical desktop workflow used Codex Desktop for planning/review and OpenCode Desktop/TUI for implementation. On a new computer:

1. Install/sign in to Codex Desktop with the intended OpenAI account/workspace.
2. Reconnect any required plugins/apps in Codex Sources / Plugins.
3. Re-authorize provider-backed plugins; OAuth/account grants are not stored in this repo.
4. Open the target project repository.
5. If you use Superpowers in Codex as a separate workflow, install it through the Codex plugin surface available to your account. Keep that separate from TEAM V2's OpenCode profile.
6. Keep secrets in account/plugin authorization or local secure storage, never in this Git repo.

## Recommended Codex role alongside this repo

When using Codex Desktop with TEAM V2:

- architecture / plan review
- spec challenge
- final diff / PR review
- difficult fallback implementation when the DeepSeek worker fails twice

OpenCode TEAM V2 remains the heterogeneous model execution environment.
