# Security policy for this config repo

This repository is designed to be safe to publish as a private or public config repo **only if secrets remain local**.

Never commit:

- API keys / tokens
- `.env*`
- provider credentials
- SSH private keys
- OAuth refresh tokens
- MCP secrets
- exported browser/session cookies

Provider keys should remain in the provider's normal secure storage or environment variables on each machine.

The tracked OpenCode profile files reference model IDs through environment variables and do not contain provider credentials.
