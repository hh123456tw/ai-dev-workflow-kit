# Claude Code 推文設定 A/B 測試設計

**日期：** 2026-10-11
**狀態：** pilot（18 格）已完成，結果見文末「Pilot 結果」。harness 為 `claude-tweet-ab-g2`。
g1 在任何模型呼叫之前就中止了：Temp 裡的 fixture clone 遺失了 `.git/HEAD`。g2 用的是同一批 repo 和 commit，只是改放到 `~/opencode-benchmarks/repos/`。C02 從原本凍結的 source URL 重新 clone，並驗證過 commit 確實存在。
**證據位置：** `~/opencode-benchmarks/claude-tweet-ab-20261011/`（不進 repo）
**來源：** [@cyrilXBT 推文](https://x.com/cyrilXBT/status/2108867649086300218)：宣稱改一個 settings 就能讓「Opus 規劃、Sonnet 寫碼、Haiku 搜尋、critic 擋 diff」。

## 要回答的問題

1. 推文設定的**品質**有沒有比預設好？主要指標是 held-out 驗證的 strict success 和假完成率。
2. 它是否真的**省錢**？看 `total_cost_usd` 和 wall time 的分佈。
3. 推文說的分工有沒有**真的發生**？用 `modelUsage` 看各模型實際的 output token 佔比，也記錄 scout/critic 的呼叫次數、advisor 呼叫次數，以及有沒有進入 plan mode。

第 3 點在探針階段就已經有初步答案：headless 執行時，推文 arm 的主模型是 `claude-sonnet-5-5`，因為 `opusplan` 只有在 plan mode 才會切換到 Opus。

## Arms

所有 arm 都使用 `claude -p`、同一份 prompt、同一組工具，並以 `--setting-sources project,local` 排除 user settings（避免 Orca hooks 和全域 `model` 混入），同時設定 `--strict-mcp-config` 加上空的 MCP 設定。各 arm 之間唯一的差別是各自的 `--settings` 和 `--agents`。

| ID | 內容 | 用意 |
| --- | --- | --- |
| `cc-default` | `model: sonnet` | 你目前的全域預設，作為對照組 |
| `cc-tweet` | 推文設定原樣照抄：opusplan、advisorModel opus、per-model effort、`CLAUDE_CODE_SUBAGENT_MODEL=haiku`，加上 scout（haiku）和 critic（opus，原 prompt） | 處理組 |
| `cc-tuned` | sonnet、per-model effort、scout，以及要求附證據的 critic；不做全域 subagent 降級，也不開 advisor | 上一輪建議的精簡版 |

## 任務與評分

- 沿用 `claude-lane-ab-g1` 已凍結的 C01、C02、C03、C05、C06、C08。request、公開指令和 held-out verifier 都原樣複製，因此結果可以和 2026-09-23 的 Claude-lane 資料互相對照。
- 評分規則沿用 canary 修正後的版本：exit 0 但輸出 `NAME=False` 標記也算失敗；輸出改用 `cmd /c` 導向檔案；有 timeout 上限；會計算 dropped events。
- **宣稱完成的判定**：最終訊息裡出現 `STATUS: COMPLETE` 這一行。**假完成** = 宣稱完成，但 strict 驗證沒有通過。
- 執行順序是交錯排列的，用 seed `20261011` 打亂每個任務內三個 arm 的先後。一次只跑一格。

## 規模與成本

- **Pilot：** attempt 1，共 18 格。參考上一輪的數據（claude-core 每格中位數 $3.25，C05 約 $11），估計約 **US$60–90**，執行時間約 **4–6 小時**。
- **完整版：** 加跑 attempt 2，共 36 格，成本和時間都約為兩倍。之前的資料顯示 wall time 在不同 run 之間可以相差到 4 倍，所以至少要跑 2 次才能看分佈。
- **檢定力：** 每個 arm 只有 6 個任務，測不出細微的通過率差異。能測出的是假完成率的大幅差異、成本差異，以及「誰真正在做事」。

## 已知限制

- **headless 模式不會進入 plan mode。** `opusplan` 在這裡等同於 Sonnet。這反映的是自動化和非 plan mode 的日常使用情境，並不代表互動式先 plan 再執行的情境。結果解讀時必須註明這一點。
- **任務屬於 in-sample。** 這些任務原本是為了調校 Core 而挑選的，不過三個 arm 都同樣不帶 Core gate，所以對各 arm 是公平的。
- **advisor 是實驗性功能**，且只能透過 Anthropic API 使用。如果 `advisor_calls` 一直是 0，代表這個設定沒有產生任何作用。

## 執行

```
cd ~/opencode-benchmarks/claude-tweet-ab-20261011
python bench.py show C01 cc-tweet   # 乾跑，印出完整的呼叫指令
python run-all.py                   # pilot：18 格
python run-all.py --all             # 補跑 attempt 2
python bench.py aggregate           # 產生 aggregate.md
```

## 判讀規則（事先寫定）

- 推文設定要算「值得用」，必須同時符合以下三點：
  - strict success 不低於 `cc-default`；
  - 假完成次數不高於 `cc-default`；
  - 中位成本或 wall time 至少有一項明顯較低（≥20%）。
- 如果 `cc-tweet` 的 output token 中 Sonnet 佔比 ≥90%，而且 critic 和 advisor 都沒有被呼叫，結論就是「推文描述的分工在實際執行中沒有發生」。

## Pilot 結果（2026-10-11，attempt 1，共 18 格，全部有效）

| arm | strict | 宣稱完成 | 假完成 | 中位 wall s | 中位 $ | 總 $ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cc-default | 2/6 | 5 | 3 | 114 | 0.36 | 2.08 |
| cc-tweet | 3/6 | 5 | 2 | 131 | 0.44 | 2.63 |
| cc-tuned | 3/6 | 3 | 1 | 118 | 0.40 | 2.52 |

**實際分工：** 18 格中，Sonnet 的 output token 佔比全部是 100%。subagent（包括 scout、critic，以及內建的 Explore 和 general-purpose）被呼叫 0 次，advisor 被呼叫 0 次，plan mode 也從未進入。

**依事先寫定的判讀規則：**
- `cc-tweet` 不符合「值得用」的門檻：成本比 `cc-default` 高約 26%，wall time 高約 14%，兩者都沒有降低。
- 推文描述的分工完全沒有發生。三個 arm 實質上都是 Sonnet 單模型在跑，arm 之間唯一真正生效的差異只有 Sonnet 的 effort 設定。
- strict 的差距（2/6 對上 3/6）只來自 C03 一題，以 n=6 的樣本來看屬於雜訊。
- 假完成次數是 3 / 2 / 1，方向和 `cc-tuned` 的「要求證據」設計一致。不過 critic 從頭到尾沒被呼叫，所以這個差異無法歸因於 critic。

**成本：** pilot 實際總花費約 US$7.2，耗時約 55 分鐘，遠低於原先估計的 US$60–90。原因是這幾題 Sonnet 都沒有委派 subagent，單格的中位數約 $0.4。

**結論：** 這套設定的效果取決於模型是否主動委派任務，而在這 6 個真實任務裡，模型一次都沒有委派。照原設計再補跑第二輪，量到的只會是 effort 設定的雜訊，因此不建議照原樣補跑。如果要測「分工本身有沒有幫助」，需要另外設計一個在 prompt 裡強制使用 scout 和 critic 的 arm。
