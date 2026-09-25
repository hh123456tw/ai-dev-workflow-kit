# Claude Code 個人 skills 備份

這裡備份的是 `~/.claude/skills` 的**清單與來源**，不是 skill 檔案本身。第三方 skills 留在上游，換電腦時照清單重裝即可。

| 檔案 | 內容 |
| --- | --- |
| `manifest.json` | `~/.claude/skills` 每一個項目與它的來源 |
| `skill-lock.json` | skills CLI 的 lock 檔副本（來源 repo、路徑、資料夾雜湊，不含憑證） |

更新備份（裝了新 skill 之後）：

```powershell
python scripts/export-claude-skills.py
```

## 來源與還原方式

| 來源 | 還原 |
| --- | --- |
| `gstack`（`garrytan/gstack`，版本與 commit 見 `manifest.json`） | `git clone https://github.com/garrytan/gstack.git ~/.claude/skills/gstack`，`git checkout <commit>`，再執行 `./setup`；`gstack-*` 資料夾由 setup 產生 |
| `skills-cli`（`mattpocock/skills`、`heygen-com/hyperframes`） | 用 skills CLI 依 `skill-lock.json` 的 `source` 與 `skillPath` 重裝，例如 `npx skills add mattpocock/skills` |
| `local-symlink`（paperclip 系列） | 先取得 `C:\codex\paperclip`，再重建 symlink 指向 `manifest.json` 裡的 `target` |
| `claude-account-sync`（`synced/`） | 綁定 claude.ai 帳號，登入後自動同步，無法從檔案還原 |

注意：skills CLI 的確切指令與旗標以它當時的版本為準；這份清單保證的是「裝了什麼、從哪裡來」。

`claude-core` lane 會刻意隱藏這裡所有個人 skills，只保留 Core 的 6 個。
