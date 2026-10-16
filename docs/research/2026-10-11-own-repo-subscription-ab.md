# 自有 repo 任務：Claude Code（Max 5x）vs OpenCode Core（ChatGPT GPT-5.6）

**日期：** 2026-10-11
**Harness：** `own-repo-ab-g1`
**證據位置：** `~/opencode-benchmarks/own-repo-tasks/`（不放在這個 repo 裡）
**要回答的問題：** 在不降低品質的前提下，哪一個訂閱可以省掉？這一版是最小版：10 題，每題跑 1 次。兩個 arm 都扣各自訂閱的額度，沒有產生額外費用。

## 題目

- 題目從使用者自己的 repo 挖出來：qingpu-insight 6 題、agentforge 4 題。
- 每題都是一個真實 commit。起點是它的 parent，hidden test 是這個 commit 改動的 `tests/test_*.py`（加上 fixtures）。`mine.py` 挖題時驗證過一次，`bench.py validate` 又用 benchmark 專用的 venv 重新驗證過：在 parent 上會 FAIL，套上 commit 後會 PASS。
- 題目描述是 issue 形式，由 subagent 依 commit 和非測試的 diff 起草，我逐題檢查過，沒有洩漏測試程式碼。不過 qp-097d734、qp-bd7a82c、af-4a22606 這三題的規格包含 hidden test 會逐字比對的字串和範例，題目因此變簡單。兩個 arm 看到的題目完全一樣，所以對相對比較公平。
- 兩個 arm 都使用 `envs/` 下的 benchmark 專用 venv，不會動到 repo 原本的 `.venv`。

## 結果

| arm | strict | 宣稱完成 | 假完成 | 中位 wall | p90 wall | Claude API 等值 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cc-default（Claude Sonnet 5.5，Max） | **8/10** | 7 | 2 | **6.2 分** | 14.4 分 | $5.71（扣 Max 額度） |
| oc-core（GPT-5.6 Sol + DeepSeek，ChatGPT） | **8/10** | 10 | 2 | **18.5 分** | 42.1 分 | — （扣 ChatGPT 額度） |

- **兩組每一題的結果都相同。** 兩組都在同樣兩題失敗：af-73052cf（dashboard）和 qp-bd7a82c（591 API；描述中整棟建物 floor 的格式寫得不夠清楚，起草時就已註記為模糊點）。成對比較的通過率差 = 0。
- **假完成：** 兩組都是 2 次，就是那兩題失敗的題目。
- **Claude 回報比較保守：** 有 3 次實際通過、卻回報 `INCOMPLETE`，原因是它自己跑完整測試時逾時。oc-core 每一題都宣稱完成，並附上 Core 的完成收據。
- **速度：** Claude 中位數大約快 3 倍。oc-core 的時間包含 Core gate、風險分類和 review 的額外開銷。
- **其他：** 沒有出現 ChatGPT 429，也沒有 hidden test 卡住。

## 結論與限制

- 在這 10 題上，兩種工作流的品質一樣，差別只在速度：Claude 比較快。
- **限制：**
  - 只有 10 題，每題只跑 1 次，信賴區間很寬。只能說「沒看到品質差異」，不能說「品質相同」。
  - 題目只來自兩個 repo，其中 qingpu 的 6 題都集中在 listing/radar 這一塊。
- **訂閱上的意義：**
  - 純寫程式的話，任一個訂閱都能完成這類任務。
  - Claude 快約 3 倍，而且 Max 額度用不完。如果 ChatGPT 只拿來寫程式，它的方案是最可以考慮降級的。
  - 反過來，退掉 Max 不會損失品質，但會變慢約 3 倍。
- **下一步：** 如果要把結論變穩，需要擴大到 30 題、每題跑 2–3 次，並修正 qp-bd7a82c 的規格。

## 過程紀錄

- **第一次 run-all 失敗：** 由 Claude 工具在背景啟動的 `run-all` 不明原因中止，留下一個孤兒 `claude -p`。處理方式是終止它，把它的 run 封存到 `aborted/`，再改用獨立的 `Start-Process` 重新執行，之後全程正常。
- **smoke 格：** `qp-931cc75` 兩個 arm 的 smoke 結果都直接沿用，納入正式結果（同一個 harness generation、同一份凍結的 manifest）。

## 加測：快速測試規則（2026-10-12，`own-repo-fast-g1`）

**規則內容**（`fast-test-rules.md`）：

- 修改過程中只跑相關的測試。
- 完整測試只在最後跑一次；只有在環境說明標明可平行時，才加上 `-n auto`。
- 已經通過的測試不重跑。
- 互不相關的讀檔動作合併成一步。

**套用方式：**

- Core 版在上述規則之外，再加兩條：題目已指明檔案時不派 explorer；reviewer 與最後一次回歸測試同時執行。這些規則加在 benchmark 複製出來的 `core-lead.md` 副本尾端，已部署的 Core 沒有改動。
- Claude 版透過 `--append-system-prompt` 加入規則。

**平行測試的安全性實測：**

- qingpu：完整測試串行與 `-n auto` 都是 exit 0，115 秒降到 50 秒。
- agentforge：串行 108 個全過；`-n auto` 下 32 個失敗、41 個錯誤，判定不可平行。

| arm | strict | 假完成 | 中位 wall | 總 wall 相對基準 | 每題中位比 |
| --- | ---: | ---: | ---: | ---: | ---: |
| cc-default | 8/10 | 2 | 6.2 分 | — | — |
| **cc-fast** | 8/10 | 1 | **3.7 分** | **0.74** | **0.66** |
| oc-core | 8/10 | 2 | 18.5 分 | — | — |
| **oc-core-fast** | **9/10** | 1 | **16.7 分** | **0.73** | **0.72** |

**oc-core 的機制驗證**（統計工具呼叫的耗時）：

| 項目 | oc-core | oc-core-fast |
| --- | ---: | ---: |
| pytest 總時間 | 94 分 | 61 分（−35%） |
| 完整測試次數 | 約 26 次 | 約 12 次 |
| 使用 xdist 的次數 | 0 | 10 |
| subagent 等待時間 | 56 分 | 57 分（**沒有改變**） |

只有測試相關的規則有效。不派 explorer、reviewer 與回歸測試並行這兩條，實際上沒有發揮作用。

**結論：**

- 兩組都快了約 26–34%，品質沒有下降：cc-fast 8/10 對 8/10，oc-core-fast 9/10 對 8/10。qp-bd7a82c 第一次通過，可能是運氣。
- 依事先寫定的門檻（品質不低於基準，且 wall 降低 ≥25%），**兩組都通過**。

**限制：**

- 基準是前一天跑的。
- 每題只跑 1 次，總共 10 題。
- 有幾題反而變慢：af-2ee1366 / af-7b2ec5a 的 cc-fast、af-4a22606 / qp-f72a686 的 oc-fast。單題的時間變異很大。

**下一個槓桿：** subagent 等待時間（56 分，約佔 28%）完全沒有減少，需要改 Core 的 review 觸發機制或 dispatch 方式，光靠 prompt 提示不夠。

## 加測：現行 Claude Code、Ponytail、milktea（2026-10-16，`own-repo-plugins-g2`）

**這輪要回答的問題：** 在使用者實際的 Claude Code 上，加裝熱門的 skill 和 plugin，能不能讓結果更好或更快？

**四個 arm：**

- `cc-current`：使用者實際的 `~/.claude` 設定，包含 hooks、plugins、MCP，以及含快速測試規則的全域 `CLAUDE.md`，完全不做隔離。
- `cc-ponytail`：`cc-fast` 加上 Ponytail 5.2.0（full mode）。
- `cc-milktea`：milktea `implement` 強制跑完整流程，Claude 當 Developer，Codex 當 Reviewer A 和 B，再加上 Ponytail 與 i-have-adhd。
- `cc-milktea-auto`：與 `cc-milktea` 相同，但讓 lead 自己決定要不要跑完整流程。

兩個 milktea arm 都跳過 grill-me，直接把 request 當成已核准的 spec，並拆成一張 ticket。

| arm | strict | 假完成 | 10 題總 wall | 相對 cc-fast |
| --- | ---: | ---: | ---: | ---: |
| cc-fast（2026-10-12 基準） | 8/10 | 1 | 47 分 | — |
| cc-current | 7/10 | 3 | 42 分 | 0.90 |
| **cc-ponytail** | 7/10 | 3 | **33 分** | **0.70** |
| cc-milktea-auto | 8/10 | 2 | 48 分 | 1.01 |
| cc-milktea | 8/10 | 1 | 231 分 | **4.92** |

**af-4a22606 重跑（每個 arm 4 次）：**

- cc-ponytail 過 1/4，cc-current 也過 1/4，失敗原因相同：都把 `:(exclude,literal)` 的 pathspec 傳給 `git add`。
- 單次跑時兩組少過的這一題，是題目本身容易隨機失敗，不是 Ponytail 造成的。cc-fast、cc-default、milktea 在這題上都只跑過 1 次，而且都通過。

**結論：**

- **Ponytail：** 品質和 cc-current 一樣，10 題總時間少 23%（相對 cc-fast 少 31%），lead 的 output token 少 17%。方向和 JetBrains 的獨立實測一致（−11% 時間）。**已採用**，裝進日常 Claude Code。
- **milktea 強制完整流程：** 通過與失敗的題目和其他 arm 完全一樣，兩個 Codex Reviewer 沒有救回任何一題，時間卻是 4.9 倍。另外，Codex 的 sandbox 在這台 Windows 上起不來（`setup refresh had errors`），Reviewer 只能做靜態審查。
- **milktea-auto：** 在小任務上，lead 會略過 Developer 和 Reviewer 的流程（「改動只有一行」），結果等於 cc-fast，沒有額外好處。
- **cc-current：** 使用者另外裝的 plugin，在這類任務上沒有明顯加分。
- **i-have-adhd：** 只改輸出格式，沒有獨立量測，依使用者偏好安裝。

**過程紀錄：**

- **OOM：** 使用者的本機 LLM `strata` 佔用約 32 GB commit，加上 milktea 巢狀的 CLI，耗盡了 64 GB commit。11 格封存到 `aborted/oom-20261016/`。之後加上記憶體門檻（每格前要有 ≥8 GB free commit，milktea 要 12 GB），每格結束後也會清除殘留的子程序。
- **重開機後 BIOS 虛擬化被關閉**（`HCS_E_HYPERV_NOT_INSTALLED`）：Docker 和 WSL2 無法啟動，agentforge 的 Postgres 不可用。受影響的 2 格封存到 `aborted/no-docker-20261016/`，修好後重跑。
- **排序：** 為了讓 smoke 那格排第一，排序時把所有 `cc-milktea` 排到最前，結果這組集中在同一段時間跑完，沒有和其他 arm 交錯。
- **限制：** 每題 1 次，只有 af-4a22606 跑了 4 次；cc-fast 是前幾天的基準；cc-current 會隨使用者設定的變動而改變。
