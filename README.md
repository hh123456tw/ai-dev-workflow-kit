# ai-dev-workflow-kit

可攜的 AI 開發工作流設定，涵蓋兩個 harness：

- **OpenCode**：Vanilla、Stable、Core 三套互相隔離的模式（`oc-vanilla`、`oc-stable`、`oc-core`）。
- **Claude Code**：Core 規則的 Claude 版本（`claude-core` 用 Max、`claude-ds` 用 DeepSeek），附決定性的 completion gate，見下方〈Claude lane〉。

另外備份 Claude Code 個人 skills 的清單與來源（gstack、Matt Pocock skills 等），見 [`claude-skills/`](claude-skills/README.md)。實測結果見 [`docs/research/2026-09-23-claude-lane-benchmark.md`](docs/research/2026-09-23-claude-lane-benchmark.md)。

本 repository 只保存設定與還原腳本；憑證、OAuth 狀態、快取及第三方框架原始碼都留在本機。

OpenCode 在新電腦 clone 之後是**三步**：先跑一次 setup 讓 plugin 被宣告，在 Stable 啟動一次 OpenCode 讓 Superpowers plugin 安裝，再跑一次 setup 部署 Core skills（剩下只需 `opencode auth login`）。

## 三種模式

| 模式 | 用途 | 預設 agent | Superpowers |
|---|---|---|---|
| **Vanilla** | 完整 upstream Superpowers，作為 reference 與最大嚴謹度 fallback | `build`（OpenCode 內建） | 完整 plugin／bootstrap |
| **Stable** | 安全日常模式，現有 cost-control／one-writer／bounded delegation／reviewer 規則 | `stable-lead` | 完整 plugin／bootstrap |
| **Core** | Hackathon／MVP 快速自主模式 | `core-lead` | 6 個精選 skills 加 OpenCode 內建，**不載入 bootstrap** |

### Core 的精選 skills

Core 暴露以下六個精選 skills，並隱藏重型 skills：

1. `test-driven-development`
2. `systematic-debugging`
3. `verification-before-completion`
4. `requesting-code-review`
5. `receiving-code-review`
6. `finishing-a-development-branch`

Core 刻意**不暴露**：`brainstorming`、`writing-plans`、`subagent-driven-development`、`using-git-worktrees`。

## 為什麼是三種

實測 3 個任務（從零建立 CLI、既有專案加功能、regression bugfix），每個 valid run 都通過 public 與 agent 看不到的 hidden tests：

| 工作流 | Runs | Pass | 平均時間 | Session 拓撲 | 平均 DeepSeek 成本 |
|---|---:|---:|---:|---:|---:|
| Vanilla | 3 | 3/3 | 18m 26s | 2–17（不固定） | $0.0988 |
| Stable | 9 | 9/9 | 9m 52s | 固定 2 | $0.0170 |
| Core | 9 | 9/9 | 6m 5s | 固定 2 | $0.0163 |

Core 相對 Stable：快 38.3%、input token 少 37.7%、output token 少 47.6%，hidden test 通過率相同。

Vanilla 功能正確但拓撲不固定（2 到 17 個 session），時間與成本變異大，不適合時間有限的單人 MVP。

完整理由見 [`docs/superpowers/specs/2026-09-19-three-mode-opencode-workflows-design.md`](docs/superpowers/specs/2026-09-19-three-mode-opencode-workflows-design.md)。

## 為什麼必須隔離

三種模式不能靠切換 agent 實作，因為 **plugin 載入發生在 process／config 層級**：

- Vanilla 與 Stable 需要完整 Superpowers plugin 與 bootstrap。
- Core 必須完全看不到 bootstrap 與重型 skills。

因此 Core 使用獨立的 config dir、獨立的 `XDG_CONFIG_HOME`，並停用外部 skills。CLI 的 Core launcher 另外以 `--pure` 執行；Desktop 的 Core wrapper 因為 Electron 不會把 `--pure` 傳給 OpenCode sidecar，改用上述隔離的 config dir／`XDG_CONFIG_HOME` 達成同樣效果。Core 刻意**不**停用預設 plugins，因為那會一併移除解析 pinned model 所需的內建 provider plugins。這已用 `opencode debug config` 與 `opencode debug skill` 驗證：Core 看到六個精選 skills、看不到重型 skills，plugin 為 none。

## 入口

### CLI

```powershell
oc-vanilla    # 完整 Superpowers，build agent
oc-stable     # 完整 Superpowers，stable-lead
oc-core       # 自主 Core，--pure，隔離 config
```

### OpenCode Desktop

| 捷徑 | 模式 | user-data-dir |
|---|---|---|
| 原本的 **OpenCode** | Stable | `%APPDATA%\ai.opencode.desktop` |
| **OpenCode Vanilla** | Vanilla | `%APPDATA%\ai.opencode.desktop-vanilla` |
| **OpenCode Core** | Core | `%APPDATA%\ai.opencode.desktop-core` |

**重要限制（已實測）：OpenCode Desktop 1.18.31 一次只能開一個實例。** 實測結果是：在既有實例執行中，用不同的 `--user-data-dir` 啟動 `OpenCode.exe` 會立即以 exit 0 結束，自訂目錄完全沒有被寫入，預設的 `lockfile` 也沒有變動。已用三個不同目錄與兩種參數形式重現。

原因是 app 呼叫 `requestSingleInstanceLock()` 後失敗就退出，而這個版本的 lock **不以 `--user-data-dir` 區分**。

所以：

- 三個 Desktop 捷徑是**替代入口，不是可同時開啟的視窗**。要換模式就關掉目前這個再開另一個。
- **CLI 的三個 launcher 不受影響**，它們是獨立 process，可以同時執行。
- Core 的 config 隔離在 Desktop wrapper 下仍然有效，只有「並存」不可用。

**原本的 OpenCode 捷徑不會被修改。**

### Slash command

`/stable` 可用於 Vanilla 與 Stable 兩個模式。Core 使用自己的 `core-lead`，其隔離 config 目錄不含 `commands/`，因此**不暴露 `/stable`**。

## Core 的行為

- 規格清楚就直接開始實作，不開設計批准迴圈。
- 可逆的歧義自己選最簡單的合理解釋、記錄下來、繼續做。
- 只有這幾種情況會停下來問：不可逆／破壞性操作、安全或憑證決策、破壞性資料或 schema migration、缺少只有你能提供的存取權。
- 預設自己實作；只有四條件全部成立才委派一位 DeepSeek worker（互斥檔案所有權、不共用 state／schema／config、獨立驗收、可獨立回滾）。
- 同一時間只有一位寫入者。
- reviewer 採 deadline-aware。Production 檔案指 tests／文件／fixture／範例／生成物以外的 tracked 檔案；會影響行為、build、打包或部署的 runtime config／package manifest 也算。Build 在兩個以上 production 檔案時必審；Feature Freeze 必須再命中 `demo_path`／`cross_module`／`concurrency`／`shared_state`／`external_api`，Demo Survival 必須再命中 `concurrency`／`shared_state`／`external_integration`／`demo_blocking_cross_module_crash`。每個 changed file 都要分類，所有 flag 都要記 true／false 與受影響路徑，才能使用 `review_not_required`。指定 reviewer 是唯讀 `reviewer`；`explorer` 不可替代。
- 必要 reviewer 無法執行（失敗、被拒絕、逾時、沒有回傳結果）就是 `verification_blocked`：可以回報實作與決定性證據，但**不得宣稱完成**；沒跑過的必要 review 永遠不算通過。
- 宣稱完成需要一份 completion receipt：deadline mode、改動檔案數、逐檔分類、risk flags 與路徑、review 觸發判定、指令與其確切結果及 exit code、驗收覆蓋、reviewer 狀態與發現、範圍聲明、任何受阻條件。所有 Critical／Important 發現必須解決並重新驗證後才能完成。
- tests／typecheck／lint／build／smoke 對其涵蓋範圍是權威，但**不足以構成完成**。
- 數值／效能／並發／快取／資源類驗收條件，必須量測請求所指的真實指令、API 或執行路徑；mock 時鐘、合成計數器、實作內部細節或自製替代指標都不算證據。

## Windows 安裝

### CodeGraph-only Core canary（已退役）

配對 benchmark 未達 promotion rule，且正式證據不足，因此 CodeGraph 沒有
升級進正常 `oc-core`。Treatment config、launcher 與 CLI shim 已移除；
`scripts/install-codegraph-windows.ps1` 僅保留作研究／重跑工具。完整結果與
限制見 `docs/research/2026-09-20-codegraph-core-canary.md`。

前置需求：Git、Node.js/npm、OpenCode、PowerShell，以及安裝 gstack 所需的 Git Bash 或 WSL。

```powershell
git clone https://github.com/hh123456tw/ai-dev-workflow-kit.git
Set-Location ai-dev-workflow-kit
Set-ExecutionPolicy -Scope Process Bypass
./scripts/setup-windows.ps1
```

setup 會依序：

1. 備份全域 config、agents、commands、modes（保留最新 3 份備份），隨即清理已退役的 CodeGraph canary 部署物。
2. 安裝／更新 gstack。
3. 部署共用全域 agents 與 commands。
4. 部署三個 mode 目錄與正常 launcher scripts。
5. 從已安裝的 Superpowers 套件複製 6 個 Core skills（**要求 6.3.0**，版本不符會明確失敗，不靜默降級）。
6. 安裝 `oc-vanilla`／`oc-stable`／`oc-core`，建立兩個 Desktop 捷徑，並列出待清理的舊產物。

步驟 5 需要本機已快取 Superpowers 套件。全新機器第一次執行 setup 時它還不存在，setup 會明確失敗並提示：先在 Stable 啟動一次 OpenCode 讓 plugin 安裝，再重跑 setup。這是預期行為，不會靜默降級成完整 plugin。

`~/.config/opencode/opencode.jsonc` 已存在時，setup 只會警告並保留原檔。

舊產物（`team-*`、`profiles/`、`ensemble.*`、`oc-product`）加 `-CleanLegacy` 一次清除。

## macOS/Linux 安裝

```bash
git clone https://github.com/hh123456tw/ai-dev-workflow-kit.git
cd ai-dev-workflow-kit
chmod +x scripts/*.sh
./scripts/setup-unix.sh
```

Unix 只提供三個 CLI launcher，不建立 Desktop 捷徑（Desktop 捷徑是 Windows-only）。舊產物清理用 `--clean-legacy`。

與 Windows 相同，步驟 5 需要本機已快取 Superpowers 套件。全新機器的第一次 setup 會明確失敗；先在 Stable 啟動一次 OpenCode 讓 plugin 安裝，再重跑 `./scripts/setup-unix.sh`。

## Claude lane（claude-core / claude-ds，Windows）

Core 規則的 Claude Code 版本。兩條 lane 載入同一套規則（[`modes/claude/core/CORE.md`](modes/claude/core/CORE.md)）、同樣 6 個精選 skills、唯讀的 `kit-core:reviewer` / `kit-core:explorer`，以及決定性的 **completion gate**。

| Lane | 後端 | 認證 |
| --- | --- | --- |
| `claude-core` | Claude Max（官方 `claude` CLI） | CLI 自己的 `/login`；清掉所有 `ANTHROPIC_*` 覆寫與 Claude Desktop 宿主變數 |
| `claude-ds` | DeepSeek Anthropic 相容端點 | `DEEPSEEK_API_KEY`；獨立 `CLAUDE_CONFIG_DIR`，碰不到 Max；所有模型別名釘在 `deepseek-flash`（避免 opus 被映射到 v4-pro） |

安裝（不會寫入 `~/.claude`）：

```powershell
pwsh -NoProfile -File scripts/setup-claude-lane.ps1
```

**Completion gate** 是 plugin 內的 hook（[`kit_gate.py`](modes/claude/core/plugin/hooks/kit_gate.py)）：SessionStart 記錄基準，PostToolUse / PostToolUseFailure 記錄實際執行的指令與真實 exit code、reviewer 派遣；Stop 時只要本 session 有檔案變更，就要求 `.claude-kit/receipt.json`，並自行重算 review 門檻、比對證據。`incomplete` / `verification_blocked` 只要說明原因就放行；連續擋 3 次後放行但顯示 `COMPLETION GATE FAILED`。

每次啟動 launcher 都會建立專屬的 verdict 檔（`CLAUDE_KIT_VERDICT_FILE`），gate 每次 Stop 都寫入。Session 結束後，只有 `pass`、`no_changes`、`no_repository` 維持 exit 0；`blocked`、`gate_failed`、`gate_crashed` 或完全沒有 verdict（gate 崩潰、逾時、未啟動、session 被中斷）都會在 stderr 說明並以 **exit 3** 結束，無人值守的 `-p` 執行也看得到。歷史紀錄另存於 `<git-dir>/claude-kit/`。

驗證指令只接受單一指令或 `&&` 串接；含 `;`、`|`、`||`、單獨的 `&` 或換行的指令不能證明通過（引號內的文字不算）。

已知限制：
- `deadline_mode`、risk flags 與 "generated" 降級理由仍由 agent 自行申報，gate 只能檢查一致性，無法驗證真偽。
- Gate 只檢查 session 開始時所在的 repo；session 中途 `cd` 到另一個 repo 所做的變更不會被檢查。
- 出錯結束的 reviewer 也會被 SubagentStop 記為完成；gate 只確認 `kit-core:reviewer` 跑完，不解讀它的結論。
- `git -C . reset --hard`、`git.exe clean` 這類變形可以繞過 deny 規則（OpenCode 版本也有同樣的限制）。
- 「可證明的指令」判斷是啟發式的：引號解析沒有完整模擬 Bash / PowerShell 的轉義規則，刻意構造的指令（例如 `bash -c "pytest; true"`）仍可能過關。它擋的是無心的 `| tail`、`; echo`，不是蓄意造假。`claude-ds` 開啟 `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` 保護 token，Claude Code 會因此強制 default 權限模式，自動化執行請明確給 `--allowedTools`。Unix launcher 尚未提供。

## 驗證

```powershell
pwsh -NoProfile -File tests/profile-bundle.acceptance.ps1
python -m pytest tests -q
```

## 後續研究

Core 的下一階段候選是 **Risk-Routed Hybrid Core**：用便宜的 decision layer 在 GPT-5.6 被呼叫之前決定 execution tier，讓 GPT-5.6 只處理真正困難、高風險的工作。目前僅完成研究，尚未實作。

見 [`docs/research/2026-09-19-jev-risk-routed-hybrid-core.md`](docs/research/2026-09-19-jev-risk-routed-hybrid-core.md)。

## 安全性

絕不可 commit provider 憑證、OAuth 狀態、worktree 或 runtime database。詳見 [SECURITY.md](SECURITY.md)。

## 上游專案

- [OpenCode](https://opencode.ai/)
- [Superpowers](https://github.com/obra/superpowers)
- [gstack](https://github.com/garrytan/gstack)
