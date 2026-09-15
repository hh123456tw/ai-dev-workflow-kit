# Original Design Brief (source of truth)

Archived 2026-09-15 from the founding prompt. This document is the design
authority for the STABLE / TEAM dual workflow. Agent configs, commands, and
checklists implement it; when they conflict with it, this brief wins until it
is amended here.

No credentials are contained in this file.

---

我要建立兩套互相獨立、用途不同的 AI 開發 Workflow：

1. STABLE MODE
   = 慢一點，但高可靠、高驗證性，適合正式專案、Side Project、求職作品。

2. TEAM MODE
   = 真正 Parallel Multi-Agent，適合 Hackathon、MVP、Prototype、短時間快速開發。

兩套 Workflow 共用：

* OpenCode
* GPT-5.6
* DeepSeek V4.1 Flash
* gstack 精選工具

但：

STABLE 使用 Superpowers。

TEAM 使用 Matt Pocock Skills + OpenCode Ensemble。

不要讓 Superpowers 與 Matt Pocock 在同一個 Primary Agent workflow 中同時自動作用。

```
                OpenCode
                   │
      ┌────────────┴────────────┐
      │                         │
  STABLE MODE               TEAM MODE
      │                         │
 GPT-5.6 Lead              GPT-5.6 Lead
      │                         │
 Superpowers              Matt Pocock
      │                         │
DeepSeek Worker          OpenCode Ensemble
concurrency = 1                 │
┌───────┼───────┐               │
▼       ▼       ▼               ▼
DS      DS      DS           Workers A/B/C
```

核心原則：

Stable: Reliability > Speed
Team: Speed + Isolation > Maximum Process Strictness

共同原則：

Strong model thinks.
Cheap model executes.
Tests decide.
Workers cannot approve themselves.
Parallelism only where dependencies allow.

## STABLE MODE 流程

idea → brainstorm → design → plan → worktree → DeepSeek implementation →
TDD (RED → GREEN → REFACTOR) → review → verification → merge

concurrency = 1，預設不啟動 Ensemble。

## TEAM MODE 流程

grill-lite → MVP scope → to-spec → to-tickets (vertical slices) →
Dependency DAG → Ensemble parallel workers → integration → review → QA → demo

concurrency 預設 3（2–3，完全獨立才 4）。Dependency-driven scheduling，
不是 wave barrier。One ticket = one branch = one worktree。

## gstack 定位

不是第三個 primary methodology，是兩套共用的 Specialist Toolbox
（QA / Review / Security / Ship / CEO Review / Design Review /
Benchmark / Investigate），用 namespaced commands 避免衝突。

## 上下文隔離 / 模型路由 / 上報規則 / 反作弊

* Worker 只拿最小上下文；reviewer 用 fresh context。
* GPT-5.6 做需求、架構、spec、ticket、整合、終審；DeepSeek 做探索、
  實作、測試、機械重構。
* Worker 不得重定義需求；架構衝突、破壞性 DB 變更、安全設計一律上報。
* 禁止刪測試、放水斷言、偽造成果、自己批准自己。

## 入口

/stable <request> → stable-lead + Superpowers
/team <request> → team-lead + Matt Pocock + Ensemble
(/fast 可選，複雜就先不做)

## Definition of Done

Acceptance GREEN (lead 親見) + regression GREEN + typecheck/lint GREEN +
independent review PASS。No PASS without executed evidence.
