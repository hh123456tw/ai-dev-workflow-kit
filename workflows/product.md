# PRODUCT workflow

## Stack

- Primary model: GPT-5.6 Sol (product lead / planner / reviewer; actual provider/model ID supplied locally)
- Worker model: DeepSeek V4.1 Flash (scoped implementation; actual provider/model ID supplied locally)
- gstack: product/CEO/engineering/design/QA/release workflows
- Superpowers: implementation discipline, TDD, debugging, worktrees, verification

## Intended flow

```text
Need / idea
   ↓
gstack product thinking / planning (GPT-5.6)
   ↓
Superpowers engineering discipline
   ↓
scoped implementation (DeepSeek V4.1 Flash worker)
   ↓
GPT-5.6 integration/review
   ↓
gstack QA / ship
```

## Rules

1. PRODUCT mode optimizes for fast product delivery.
2. gstack and Superpowers are allowed.
3. Matt workflow skills are hidden to prevent competing routers.
4. Provider secrets remain outside this repository.
5. Use DeepSeek V4.1 Flash for PRODUCT implementation workers; do not delegate product scope, architecture, or final approval to the worker.
6. Use worktrees when concurrent sessions would write to the same repository.
