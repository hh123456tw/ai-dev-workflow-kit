# Lean Loop：保住完成率、加快開發、降低 token 費用的 workflow

**日期：** 2026-10-11
**狀態：** 設計稿。尚未套用任何設定，也還沒做驗證。
**限制條件（不能放寬）：** 任務照樣要能完成並通過驗證。只要 strict success 或假完成率比現況差，就算失敗，省再多錢也不算數。

## 1. 依據：錢燒在哪裡

以下數字來自本機 Claude Code 紀錄（2026-09-11 到 10-11，118 個 session），按 API 價格換算，總計約 US$1,379：

| 每個請求的 context 大小 | 費用佔比 | 請求數 |
| --- | ---: | ---: |
| < 50k | 1.6% | 752 |
| 50–150k | 20.8% | 5,890 |
| 150–300k | 19.6% | 3,564 |
| **300–600k** | **31.9%** | 2,767 |
| **> 600k** | **26.1%** | 1,456 |

- **58% 的錢花在 context 超過 30 萬的請求上。** 有好幾個 session 的 context 一路長到 90 萬以上，中位數也在 35 萬到 70 萬之間。
- **前 10 個 session 佔總費用 70%，前 20 個佔 88%。** 錢集中在少數超長的 session。
- **subagent 佔 26%。** 最貴的單一 session（$207）是一個 Haiku 4.5 subagent，請求多達 2,198 次，context 最大到 89.8 萬。
- **成本的大頭是 cache，不是 output。** Opus 5.5 和 Sonnet 5.5 的 cache read 都是 $0.20/MTok，所以光是換模型，最多只省約 18%。

同一天的其他實測（`2026-10-11-claude-tweet-config-ab.md`，以及 09-23 的 Claude-lane 測試）也指向同樣的方向：

- 在 6 個真實任務上，Sonnet 單獨做的品質不比其他設定差。
- **模型不會主動委派工作。** subagent、advisor、plan mode 一次都沒被觸發。
- 強制使用 Workflow 的 arm 更慢（約 1.5 倍）、更貴，成功率也沒有比較高。
- 只看 prompt 的路由器（Laya）AUC 0.48，跟亂猜差不多。看 repo 過去的失敗率，AUC 有 0.83。

**結論：** 最大的槓桿是控制 context 長度，其次是預設用較便宜的模型。分工要由規則強制執行，不能指望模型自己去委派。

### 方案用量（2026-10-11 讀取 app 用量卡）

- 方案：Max。每週全模型用量已達 **58%**，距離重置還有 1 天 3 小時，也就是這週已過了約 84%。照這個速度，整週大約會用到上限的 **69%**。5 小時窗口用了 15%，Fable 每週額度用了 37%。
- 這個 session 自己的狀態：目前 context 27 萬，**要到 97%（約 97 萬）才會自動 compact**。這就是為什麼 session 會一路長到 90 萬以上。

**這對設計目標的影響：**

- **繼續用 Max：** 每多用一個 token 都不用多付錢。這時候省 token 的意義在於讓回應更快、保留餘裕，不在省錢。
- **想降級：** 每週用量必須壓到較低方案的上限以下。假設各方案的額度倍數是 Max 20x = 20 × Pro、Max 5x = 5 × Pro（**方案倍數與實際價格未查證**）：
  - 從 20x 降到 5x，額度會變成原本的 1/4，每週用量要降到現在的約 1/3。
  - 從 5x 降到 Pro，額度會變成原本的 1/5，每週用量要降到現在的約 1/4。
- **只做 Lean Loop 預估可省 40–55%，不夠降一級。** 要降級，還得把大量寫程式的工作移到 OpenCode：GPT 已經有訂閱，DeepSeek 走低價 API。

## 2. 設計原則

1. **一個任務一個 session，context 要設上限。** 不要讓同一段對話一路長到 90 萬。
2. **由規則決定分工，不讓模型自己判斷。** 什麼時候升級、什麼時候 review，都寫成規則，不依賴模型「自覺」去叫 subagent。
3. **驗證以可重複執行的檢查為準。** 測試、typecheck、驗收指令是完成的唯一依據，LLM review 只在符合風險條件時才觸發。
4. **升級時開新 session 並附交接文件，不把舊 context 帶過去。** 讓 Opus 帶著 70 萬的 context 接手，正是最燒錢的情況。
5. **預設不平行。** 只有互不相依、而且只讀不寫的查詢才允許平行處理。

## 3. 流程

```
① Brief  → ② Build  → ③ Gate  ─綠→ ④ Review? → ⑤ Close
   │           │          │紅            │
   │           │          └→ Stuck 規則 ──→ ⑥ Escalate（開新 session + handoff）
   └ 驗收指令先寫好
```

| 階段 | 誰做 | 規則 | 省錢或加速的原因 |
| --- | --- | --- | --- |
| ① Brief | 主模型 | 用 3–8 行寫下需求、驗收指令和不能動的範圍，存成 `HANDOFF.md` | 之後的新 session 讀這份就能接手，不必重讀整段對話 |
| ② Build | Sonnet 5.5，effort medium（OpenCode 這邊用 DeepSeek） | 自己 grep 或讀檔就好，不另外開 subagent | pilot 顯示這類任務不需要委派 |
| ③ Gate | 實際執行指令 | 只有驗收指令、測試和 typecheck 都是綠的，才算完成；最後一行要寫 `STATUS:` | 用執行結果判定，避免假完成 |
| Stuck 規則 | 規則判定 | 同一個錯誤出現 2 次，或連續 N 輪都沒有變綠，就進入 ⑥ | 依實際執行軌跡升級，不靠只看 prompt 的路由 |
| ④ Review | 沿用 Core 的風險規則 | 只有改動至少 2 個 production 檔案、而且有風險旗標時才觸發；reviewer 只看 diff 和 brief | review 的 context 很小，平常不觸發 |
| ⑥ Escalate | Opus 5.5 或 GPT-5.6，開新 session | 只帶 `HANDOFF.md`、目前的 diff 和失敗輸出 | 避免讓貴的模型讀超大 context |
| ⑤ Close | 主模型 | 更新 `HANDOFF.md`，然後 `/clear` 或關閉 session | 下一個任務從乾淨的 context 開始 |

### Claude Code 對應設定（草案，未套用）

```jsonc
// ~/.claude/settings.json，只列出需要新增或修改的部分
{
  "model": "sonnet",
  "modelSettings": {
    "claude-sonnet-5-5": { "effortLevel": "medium", "autoCompactWindow": 200000 },
    "claude-opus-5-5":   { "effortLevel": "high",   "autoCompactWindow": 200000 }
  }
}
```

- `autoCompactWindow` 的有效範圍是 100k–1M，需要 Claude Code v2.1.288 以上。本機 CLI 目前是 2.1.286，要先升級。
- 上限設 200k 是起始值，要依第 4 節的實測結果再調整。
- Stuck 規則和 Close 這兩步是寫在 CLAUDE.md 的工作規範，屬於提醒性質，無法強制執行。真正會被強制的只有 Gate，因為它看的是指令實際執行的結果。

### OpenCode Core 對應

Core 本來就有 Gate 和風險 review。需要補上的只有三項：

- Brief 和 Close 時寫 `HANDOFF.md`。
- Stuck 規則觸發時改成升級到 GPT-5.6，而且是開新 session，不在原 session 裡切換模型。
- 單一 session 的 context 上限。

## 4. 驗證計畫（判讀標準事先寫定）

benchmark 任務都很短，pilot 每格只要 $0.4，**根本不會長到 30 萬 context，所以測不到主要的成本來源。** 因此驗證分兩條線進行：

| 驗證線 | 要回答的問題 | 方法 | 費用 |
| --- | --- | --- | --- |
| A. 品質 | Lean Loop 會不會讓完成率變差？ | 用現有 harness 新增 `cc-lean` arm（帶 brief、gate 和 stuck 規則的 prompt），跟 `cc-default` 在 6 題 × 2 次上比較 | 約 US$5–10 |
| B. 成本 | 在真實使用中能省多少？ | 套用設定後正常使用 2 週，每週跑 context 分段成本報表，跟本文第 1 節的基準比較 | 不需額外花費 |

**通過條件：**

- **A：** strict success 不低於 `cc-default`，假完成次數不高於 `cc-default`，中位 wall time 不比 `cc-default` 慢超過 20%。
- **B：**
  - 每個 session 的中位費用降低 ≥ 30%。
  - context 超過 30 萬的請求，費用佔比從 58% 降到 20% 以下。
  - 這兩週內被重開、或明顯沒做完的任務數，不能比之前多。這一項由使用者自己記錄。

**預估（未驗證）：** context 上限預計可以省掉 300k+ 那一段費用的一半以上，加上預設改用 Sonnet，總費用預計降 40–55%。這個數字只是推算，要以 B 線的實測結果為準。

## 5. 刻意不做的事

- **不加 LLM 路由器。** Laya 的實測結果和 SOTA 文獻都顯示，只看 prompt 做路由在 coding 任務上無效。
- **不預設開 Workflow 或 ultracode。** 實測結果是更慢、更貴。
- **不全域把 subagent 降成 Haiku。** 最貴的 session 正是一個長 context 的 Haiku subagent，模型便宜不代表總費用低。

## 6. 便宜模型（OpenCode Go / 中國模型）要接在哪一層

**Claude Code 的 subagent 不能改用其他供應商（依官方文件）：**

- **endpoint 和憑證是整個 session 共用的。** subagent 的 `model` 只能設成 Claude 的別名或 model ID。
- **官方不支援透過 gateway 接非 Claude 模型。** llm-gateway 頁的原話："doesn't support routing Claude Code to non-Claude models through any gateway"。
- **用 Max 的 OAuth 搭 proxy 去接第三方模型，條款上沒有明說，屬於灰色地帶。** 只設 `ANTHROPIC_BASE_URL` 的話，用的仍是訂閱憑證；一旦另外設定憑證，就會改用該憑證取代訂閱。
- **OpenCode Go 本身也有限制。** 它的 `/messages`（Anthropic 格式）只提供 Haiku 5.5、MiniMax、Qwen。GLM、Kimi、DeepSeek 只走 `/chat/completions`（OpenAI 格式），Claude Code 無法直接使用。

**可行的接法：**

| 路線 | 做法 | 優點 | 代價 |
| --- | --- | --- | --- |
| A. Claude 當 lead，外包給便宜模型 | 定義一個 `cheap-worker` subagent，只開 Bash 權限，透過 Bash 執行 `opencode run --model <go 模型>`，做法和已安裝的 codex plugin 呼叫 Codex 相同 | 不需要 proxy，也沒有條款疑慮 | 兩邊的 context 要靠 `HANDOFF.md` 交接；外包的結果一定要過 ③ Gate |
| B. OpenCode Core 當主力（建議） | 在 kit 的 Core 加上 OpenCode Go provider，worker 改用 DeepSeek V4.1 Flash 或 GLM-5.2（Go 方案每月 $60 額度那一檔）；Claude 只用在難題 | 大量 token 走 $10/月的 Go 和既有的 GPT 訂閱，這是唯一能把 Claude 降級的路 | 需要在 kit 加 provider 設定，並重跑 Core 的 acceptance 測試 |

OpenCode Go：$10/月（Go Plus $40/月）。每個模型各有每月的美元額度，另外 5 小時窗口佔每月額度的 20%，每週佔 50%。
來源：https://opencode.ai/docs/go/

## 7. 實測：Claude 主導，DeepSeek 寫碼（2026-10-11，`claude-ds-ab-g1`）

- **實驗設計：**
  - 6 個凍結任務，每組各跑 2 次，共 24 格。評分方式和 `claude-tweet-ab-g2` 相同。
  - **兩組設定：**
    - `cc-default`：只用 Sonnet。
    - `cc-ds`：Sonnet 自己找要改的地方，再交給 `ds-worker` 子代理。`ds-worker` 是用 Haiku 5.5 的 relay，透過 `ds-run.py` 執行 `opencode run -m deepseek/deepseek-flash`。最後由 Sonnet 自己跑驗收。
  - **證據檔位置：** `~/opencode-benchmarks/claude-ds-ab-20261011/`

| arm | strict | 宣稱完成 | 假完成 | 中位 wall | Claude 合計 $ | 其中 Haiku relay $ | DeepSeek $ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| cc-default | **5/12** | 10 | 6 | 144 s | 5.45 | — | — |
| cc-ds | **3/12** | 9 | 7 | 323 s | 4.68 | 1.59 | 0.46 |

**各題結果：**

| 題目 | cc-default | cc-ds | 備註 |
| --- | --- | --- | --- |
| C02 | 2/2 | 2/2 | cc-ds 慢 3 倍，Claude 花費沒有減少 |
| C03 | 1/2 | 0/2 | |
| C08 | 2/2 | 1/2 | cc-ds 第 2 次的程式造成測試 deadlock |
| C01 / C05 / C06 | 0/2 | 0/2 | 兩組都沒過 |

**依事先寫定的通過條件：不通過。**

1. **品質：** strict 比對照組少 2，假完成多 1。
2. **Claude 用量：** 只少了 14%。Sonnet 本身的花費少了 43%（$5.45 降到 $3.09），但 Haiku relay 又吃掉了 $1.59。
3. **速度：** 中位數慢了 2.2 倍。C08 第 1 次 DeepSeek 兩次都撞到 540 秒逾時，最後是 Sonnet 自己完成的。

**觀察與修正：**

- **Haiku relay 的計價對不上。** Claude Code 回報的 Haiku 5.5 `costUSD`，大約等於用 $4/$20 per MTok 計算的結果，和 skill 快取的價目表（$0.10/$0.50）不符。原因還沒查清楚。不論是哪一種價格，relay 都不划算。如果要再測，應該讓 Sonnet 直接用 Bash 呼叫 `ds-run.py`，不經過 relay 子代理。
- **harness 缺陷：** `verify` 沒有設逾時。C08-cc-ds-R2 的公開 pytest 和 held-out verifier 都卡住，我在等了超過 25 分鐘後手動中止，記為失敗。下一代 harness 必須在 verify 加上逾時。
- **結論：** 以 Max 5x 這種額度用不完的情況來說，把實作外包給 DeepSeek，換來的是品質下降、速度變慢，Claude 額度卻只省一點。不建議用在正式工作上。
