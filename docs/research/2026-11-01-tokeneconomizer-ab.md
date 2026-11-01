# TokenEconomizer（Microsoft）在自有 repo 任務上的 A/B：外掛有沒有讓 Claude Code 變省

**日期：** 2026-11-01（測試於 2026-10-31 執行）
**Harness：** `own-repo-plugins-g2`（沿用，只新增 arm）
**證據位置：** `~/opencode-benchmarks/own-repo-tasks/`（不放在這個 repo 裡）。`manifest-te.json` 是鎖定的順序，`run-te.py` 是執行器，`analyze-te.py` 是配對分析，`runs/` 和 `runs.jsonl` 是原始紀錄。外掛的狀態（含 ledger）保留在 `~/opencode-benchmarks/te-home-ab/`，`analyze-te.py` 要從那裡讀外掛自己的成本紀錄。
**要回答的問題：** `microsoft/TokenEconomizer`（約 1,950 顆星，2026-10-13 建立）能不能在不降低品質的前提下，讓 Claude Code 在使用者自己的 repo 上更省？
**結論：不建議安裝。** 在這 20 組配對上，含外掛自身成本後沒有省，方向偏貴；品質沒有變差。這個測試有一個已知缺口（tool pruning 沒有在 session 開頭生效），已另外量化，見下文。

## 受測物

- **來源：** `https://github.com/microsoft/TokenEconomizer`，commit `e428fc91b0f8ffecb5a596d56b14fe2f1485a5f9`（2026-10-30），Apache 2.0，論文 arXiv 2610.22732。
- **三個機制：**
  - Micro-skills：從同一個 repo 先前的 session 學到環境事實（例如要用 `python -m pytest`），在 session 開頭注入。需要 3 個 session 確認才會注入，每 3 個 session 跑一次 proposer（會多一次模型呼叫）。預設關閉。
  - Tool pruning：把這個 repo 從沒用過的工具從請求裡拿掉。需要 5 個 session，或 2 個以上 session 共 10 個 prompt 的證據。預設開啟。
  - Loop guard：agent 卡在失敗迴圈時，由 judge 模型判斷，再插入一句提示。需要先累積 5 個正常結束的 turn 才會作用。預設開啟。
- **官方數字（論文作者量的，沒有驗證）：** 277 個 SWE-Bench 任務、6 個 repo、5 種 agent–模型組合；平均成本低 18.4–30.9%，30 個格子全部比較便宜，Pass@1 在 5 組裡有 4 組上升。每個 repo 約 46 個 session，從零開始學。
- **官方支援版本：** Claude Code 2.1.300 到 2.1.310。測試時使用者的 Claude Code 已自動更新到 **2.1.314**，超出範圍，官方說「新版本還沒測過」。試跑確認 hook 會觸發、狀態會寫入，但不保證所有行為都對。

## 安全檢查與隔離

- 先讀過程式碼：`tokeneconomizer/` 與 `plugin/` 裡沒有對外連線（只有解析 git 遠端網址的 `urlparse`）。模型呼叫透過使用者自己的 `claude -p`。
- 用 `--plugin-dir` 載入，沒有執行 `claude plugin install`，沒有改動 `~/.claude` 或使用者的設定。
- 外掛狀態放在獨立資料夾（`TOKENECONOMIZER_HOME=~/opencode-benchmarks/te-home-ab`），沒有碰預設的 `~/.tokeneconomizer`。
- 外掛會把 `/.claude/settings.local.json` 寫進 repo 的 `.git/info/exclude`。worktree 共用主 repo 的這個檔案，所以兩個真實 repo 都被改了。測試前先備份，測試後從備份還原，兩個檔案已與原本完全一致。

## 方法

- **兩個 arm（其餘設定完全相同）：**
  - `cc-b31`（對照）：Sonnet 5.5、Ponytail 5.3.1、當時的全域 CLAUDE.md 規則，不接 MCP。
  - `cc-te`（外掛）：同上，再加 TokenEconomizer，並做三個調整：`TE_MICROSKILLS=on`（預設是關的）、`TE_TOOLPRUNE_QUIET_MINUTES=0`（預設要閒置 60 分鐘才寫入名單）、每格開跑前執行 `te toolprune apply`。
- **題目：** 與先前相同的 10 題（agentforge 4 題、qingpu-insight 6 題），每題起點是 commit 的 parent，hidden test 是該 commit 改動的測試。
- **設計：** 10 題 × 2 arm × 2 次 = 40 格，依序跑。每題兩個 arm 的先後用固定種子（20261031）隨機決定，第二次與第一次對調。順序在第一格之前鎖定（`manifest-te.json`，sha256 前 16 碼 `3bf80ad50e2714bd`）。
- **為什麼重跑對照組：** Claude Code 在上一個實驗（CodeGraph）之後自動更新了，舊的對照資料版本不同，不能直接拿來配對。
- **成本：** 外掛組的成本 = 主 session 的 API 等值成本 + 外掛自己的模型呼叫。後者從外掛 ledger 的 `overhead`（以 effective token 計）按該 session 的單價換算。
- **學習範圍：** 外掛依 git 遠端網址辨識 repo，所有 worktree 共用同一份學習結果。每格結束後等外掛的背景行程結束（中位數 0.7 秒，最長 1.1 秒），才開始下一格。
- **統計：** 以（題目, 次數）為單位配對，取外掛組 ÷ 對照組的比值，對 log 比值做 10,000 次 bootstrap，報告中位數和 95% 信賴區間。
- **主要結果與次要結果：** 第 1 次（首次看到該題）是主要結果。第 2 次外掛已經看過同一題，學到的事實可能含有該題的資訊，高估真實使用情況，只當參考。

## 結果

### 全部 20 組

| 指標 | 外掛 ÷ 對照（中位數） | 95% CI | 外掛較低的組數 |
| --- | ---: | ---: | ---: |
| 模型時間 | 1.09 | 0.83–1.09 | 8/20 |
| 成本（只算主 session） | 1.04 | 0.85–1.11 | 9/20 |
| 成本（含外掛呼叫） | 1.14 | 0.91–1.17 | 5/20 |
| 工具呼叫 | 1.00 | 0.68–1.18 | 8/20 |

- strict 通過：對照 15/20、外掛 16/20。只有外掛通過的 1 組是 af-4a22606 第 1 次，這題先前重跑時兩個 arm 都只過 1/4，本來就不穩。沒有任何一組是對照過而外掛沒過。
- 外掛自己的模型呼叫約佔外掛組成本的 5.7%。
- 沒有 harness 逾時。

### 分組

| 子集 | 組數 | strict（對照/外掛） | 模型時間 | 成本（含外掛） |
| --- | ---: | :---: | --- | --- |
| 第 1 次（主要） | 10 | 8/9 | 1.07（0.82–1.12） | 1.13（0.87–1.22） |
| 第 2 次（參考） | 10 | 7/7 | 1.09（0.75–1.16） | 1.16（0.85–1.23） |
| agentforge | 8 | 5/6 | 0.95（0.67–1.07） | 0.99（0.71–1.10） |
| qingpu | 12 | 10/10 | 1.14（0.88–1.18） | **1.21（1.01–1.28）**，1/12 較便宜 |

- 依 repo 切分是事後分組，只能當線索。qingpu 的信賴區間不含 1，方向是外掛較貴。

### 三個機制實際做了什麼

- **Micro-skills：** 20 格裡有 11 格被注入事實，注入的中位數是 628 字元（約 160 個 token）。第一次注入出現在同一個 repo 累積約 4 個 session 之後。看不出對成本、時間或通過率有幫助。
- **Loop guard：** 20 格 0 次介入。這 10 題的 agent 沒有卡在失敗迴圈，沒有機會作用。
- **Tool pruning：** 見下一節。

## 測試缺口：tool pruning 沒有在 session 開頭生效

- 外掛的設計是：每個資料夾要到「自己第一次 session 結束」才拿到刪減名單。本測試每格都是新的 worktree，名單來不及用。
- 我原本在每格開跑前手動執行 `te toolprune apply` 想補上，但這一步沒有成功：20 格的 `te_denied_tools` 全是空的。
- 事後在最後一個 worktree 檢查，外掛學到並寫入了 13 個工具：`ArtifactComments`、`ArtifactData`、`CronCreate`、`CronDelete`、`CronList`、`DesignSync`、`EnterWorktree`、`ExitWorktree`、`PushNotification`、`RemoteTrigger`、`SendMessage`、`SendToProject`、`SendToProjectContext`。
- 因為 A/B 本身無法偵測小差異，改用單獨的小實驗量這個機制：同樣的請求（回覆 OK），一組不加、一組用 `--disallowedTools` 刪掉這 13 個工具，各跑 3 次，比較第一個請求的輸入 token 總數。

| 組 | 輸入 token 總數（input + cache creation + cache read） |
| --- | ---: |
| 不刪 | 37,416（三次：37,420／37,416／37,413） |
| 刪 13 個 | 36,640（三次：36,645／36,640／36,639） |

- 每個請求少約 776 個 token，**約 2.1%**。按 cache read 單價與一個 session 約 15 個請求估算，一個 session 省約 1–3% 的成本，低於 A/B 的雜訊。
- 這是在 benchmark 的設定下量的（工具被 `--setting-sources project,local` 和 `--strict-mcp-config` 限縮）。使用者平常載入很多外掛與 MCP 的環境，被刪的工具可能更多，這一點沒有測。

## 為什麼官方數字在這裡不適用

- 官方每個 repo 約 46 個 session，從零開始學。本測試每個 repo 只有 8 到 12 個 session，大部分機制要等 3 到 5 個 session 才開始作用。
- 本測試的任務多半是 1 到 10 分鐘的單次任務。外掛的固定開銷（proposer、judge）在短任務上占比較高。
- 官方題目是 SWE-Bench，使用者的 repo 與任務型態不同。
- Claude Code 版本超出官方測過的範圍。

## 結論與限制

- **結論：** 在 8 到 12 個 session 的規模下，TokenEconomizer 沒有可偵測的好處，含外掛成本後方向偏貴（中位數 1.14 倍），品質沒有變差。不建議安裝。
- **限制：**
  - 20 組配對，每格模型時間有 3 倍以上的自然波動，只能偵測約 20% 以上的差異。
  - 沒有測長期累積（數十到上百個 session）的情況，這正是官方宣稱有效的情境。
  - Tool pruning 在 A/B 中沒有生效，只用小實驗估算。
  - 第 2 次的結果可能含有同題洩漏，只當參考。
  - 模型是 Sonnet 5.5，不是使用者日常的 Opus。
  - 只用了預設的 loop guard 與 tool pruning 門檻；micro-skills 開啟、tool pruning 等待時間設為 0 都不是預設值，對外掛有利，結果仍然沒有好處。
- **何時重測：** 某個 repo 的 session 累積到上百個，或日常環境載入大量工具（例如多個 MCP）時，用該 repo 自己的 git 歷史挖題，方法同這份文件，並先確認刪減名單在 session 開頭就生效。

## 逐題資料

欄位為 對照 / 外掛。成本含外掛自身呼叫。

| 題目 | 次 | strict | 秒 | 美元 | 注入字元 |
| --- | ---: | :---: | ---: | ---: | ---: |
| af-2ee1366 | 1 | 1/1 | 573/479 | 0.67/0.70 | 0 |
| af-4a22606 | 1 | 0/1 | 369/393 | 0.79/0.52 | 0 |
| af-73052cf | 1 | 1/1 | 406/288 | 0.37/0.35 | 0 |
| af-7b2ec5a | 1 | 1/1 | 297/370 | 0.32/0.39 | 0 |
| qp-097d734 | 1 | 1/1 | 251/144 | 0.36/0.43 | 0 |
| qp-1cd6156 | 1 | 1/1 | 314/246 | 0.71/0.77 | 0 |
| qp-931cc75 | 1 | 1/1 | 53/66 | 0.07/0.10 | 0 |
| qp-bd7a82c | 1 | 0/0 | 178/212 | 0.48/0.56 | 0 |
| qp-d788d8f | 1 | 1/1 | 448/484 | 0.23/0.31 | 368 |
| qp-f72a686 | 1 | 1/1 | 184/221 | 0.23/0.14 | 368 |
| af-2ee1366 | 2 | 1/1 | 309/336 | 0.63/0.68 | 415 |
| af-4a22606 | 2 | 0/0 | 321/377 | 0.59/0.75 | 415 |
| af-73052cf | 2 | 0/0 | 543/227 | 0.59/0.26 | 719 |
| af-7b2ec5a | 2 | 1/1 | 394/281 | 0.37/0.35 | 0 |
| qp-097d734 | 2 | 1/1 | 209/295 | 0.34/0.41 | 628 |
| qp-1cd6156 | 2 | 1/1 | 291/247 | 0.63/0.77 | 628 |
| qp-931cc75 | 2 | 1/1 | 54/66 | 0.08/0.08 | 628 |
| qp-bd7a82c | 2 | 0/0 | 184/249 | 0.46/0.66 | 741 |
| qp-d788d8f | 2 | 1/1 | 168/127 | 0.24/0.29 | 741 |
| qp-f72a686 | 2 | 1/1 | 90/98 | 0.20/0.20 | 741 |

## 使用上的觀察

- 外掛在 Windows 上靠 Git for Windows 的 `sh` 執行 hook，並需要 PATH 上有 Python 3.10 以上。安裝文件要求用絕對路徑並保留 clone。
- `toolprune refresh-catalog` 會用你完整的使用者設定跑一個 session，把所有載入的工具名稱（本次是 352 個，含 Notion、Vercel 等 MCP 工具）記錄到狀態資料夾的 `catalog.json`。如果狀態資料夾要分享，要注意裡面有這份清單。
- 外掛的 proposer 和 judge 透過你自己的 `claude -p` 呼叫，用的是你自己的額度，也會載入你的使用者設定。

## 過程紀錄

- 2026-10-31 約 08:00 開跑，11:18 結束，沒有中斷，也沒有重跑。
- 開跑前一個 bench.py 的 bug 被抓到：用 Python 腳本修改檔案時，字串裡的 `\n` 被寫成真正的換行，造成語法錯誤，改用編輯工具修正後才鎖定順序並開跑。
- 清理：外掛原始碼（約 9 MB）和冒煙測試的狀態資料夾已移到資源回收筒。`te-home-ab/`（約 0.9 MB）保留作為分析的證據。兩個真實 repo 的 `.git/info/exclude` 已從備份還原。
- 本測試的腳本（`run-te.py`、`analyze-te.py`、`bench.py` 的修改）放在證據位置，沒有放進這個 repo，與先前的 benchmark 一致。
