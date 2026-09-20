# CodeGraph-only Core Canary

**Status:** Installed and smoke-verified treatment; paired A/B benchmark not yet run.  
**Pinned release:** CodeGraph `0.20.1`, Windows x64.  
**Control:** `oc-core`.  
**Treatment:** `oc-core-codegraph` with upstream `--profile=core` (8 tools).

## Isolation

This is a CodeGraph-only treatment. The normal `oc-core` config has no MCP entry.
The treatment uses the same model, `core-lead`, workers, skills, permissions, task
prompt, and acceptance checks. Do not add persistent memory, design intelligence,
Jev, model routing, or another MCP during this canary.

The first tools of interest are `get_edit_context`, `get_ai_context`, and
`symbol_search`. Record which CodeGraph tools were actually called; availability
alone is not treatment exposure.

## Install and launch

```powershell
pwsh -NoProfile -File scripts/install-codegraph-windows.ps1
pwsh -NoProfile -File scripts/setup-windows.ps1
oc-core                 # control
oc-core-codegraph       # treatment
```

The installer pins both the server and adjacent `onnxruntime.dll`, verifies each
official `.sha256` sidecar against repository-pinned hashes, and checks the binary's
reported version. The treatment launcher rechecks both the executable and
`onnxruntime.dll` hashes on every run.

## Paired A/B manifest

- Use at least 6 valid tasks, each run once in control and once in treatment.
- Freeze task prompt, repository revision, hidden acceptance, deadline mode, and
  operator intervention policy before the first run.
- Alternate order by pair (`AB`, `BA`, `AB`, `BA`, ...) to reduce warm-cache and
  learning bias. Use clean sessions and worktrees; never continue across arms.
- Pre-index treatment before timing and report that indexing cost separately. Also
  retain one cold-index measurement as an operational startup metric.
- Primary safety gate: treatment strict success and incorrect-completion rate must
  be no worse than control. Any regression stops adoption.
- Primary efficiency metric: paired change in input tokens.
- Secondary metrics: output tokens, wall time, model cost, first-pass acceptance,
  tool-call count, CodeGraph-tool utilization, and human correction/rescue.
- Report medians and every pair; do not hide a failed task in an average.

## Promotion rule

Keep `oc-core` as the default. Promote CodeGraph into normal Core only in a separate
decision after all safety gates pass and the treatment shows a repeatable input-token
or wall-time benefit on at least 4 of 6 pairs. Otherwise remove the treatment config
and launcher; the control remains unchanged.

## Installation and smoke evidence

- Server SHA-256: `aa1b6108217c119af6ac444b8652a0eadcfe2c343bff78ead2edd15b6b7b15b1`.
- `onnxruntime.dll` SHA-256: `52f8ebe8f08f369a44fed6d1cb680c7c89169795e1c2949ee25b88b538ef0948`.
- `codegraph-server --version` returned `codegraph-server 0.20.1`.
- `oc-core-codegraph mcp list` reported one connected server with
  `--mcp --profile=core`; `oc-core mcp list` reported no MCP servers.
- Read-only treatment session `ses_f40aaf0d0ffeFhTNxA647WLik1` called
  `codegraph_codegraph_symbol_search` and found `ThreeModeBundleTest` at
  `tests/test_profile_bundle.py:108`. The server reported that embeddings were still
  building and correctly fell back to name/text search.
- That smoke's first step used 9,479 input tokens and its cached final step used 344
  input tokens. This is startup evidence, not an efficiency result; only the paired
  protocol above can establish benefit.
