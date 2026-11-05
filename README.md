# NBA 2026–27 預測競賽｜三人共用自動更新版

這套網站保留 Andy、Bob、牛的固定預測，提供排行榜、逐隊誤差、東西區並排試算表、歷史走勢。資料存於同一份 `data.json`，三人看到同一個網址與歷史紀錄。

## 部署步驟（一次性）

1. 用自己的 GitHub 帳號建立一個 **Public** repository（例如 `nba-prediction-2026`）。
2. 將 ZIP 解壓縮後的**內容**上傳到 repository 根目錄；注意 `.github/workflows/update.yml` 也要上傳，且保留原本資料夾階層。
3. 到 `Settings → Pages → Build and deployment`，`Source` 選 **Deploy from a branch**，branch 選 `main`、資料夾選 `/(root)`，儲存。
4. 等 Pages 部署完成，就能分享 `https://你的帳號.github.io/nba-prediction-2026/` 給 Bob 和牛。
5. 到 `Actions → Daily NBA standings snapshot → Run workflow` 手動執行**第一次**資料更新。成功後資料會寫入 `data.json`，刷新頁面即可看到最新結果。之後會每天排程。
6. 若 Actions 無法推送檔案，至 `Settings → Actions → General → Workflow permissions` 將 `Read and write permissions` 開啟（也需確認組織政策允許）。

## 自動更新的時段與限制

- 排程是 **每日台灣時間 15:00**（UTC 07:00）；GitHub Actions 排程可能延遲，尤其整點比較容易被延後，不保證精準在 15:00 完成。
- 來源為 ESPN 未正式文件化的公開比分/排名端點（**不是 NBA 官方 API**），若端點變更、限流或網路問題，當次工作會失敗並**保留舊資料**，不寫入錯誤排名。
- 預測與歷史資料會共享；無須每天產生另一份 HTML。
- 網站載入時讀取 `data.json`，開著網頁時每 10 分鐘自動重新同步。你們看到的最後更新日期可在頁面頂部查看。
- 預測是固定資料；試算表/歷史資料依每日實際排名計算。資料管理頁的手動快照是瀏覽器本機的預覽編輯，不會寫回 GitHub；下一次同步會覆蓋本機預覽。
- GitHub Pages 公開 repository 代表預測內容和分數也可被任何知道網址的人查看；不要在程式庫中放密碼或私人資料。

## 結構

- `index.html`：互動式 Dashboard
- `data.json`：所有已成功擷取的每日排名資料
- `scripts/update_standings.py`：擷取 ESPN 排名、驗證 30 支球隊、儲存每日快照
- `.github/workflows/update.yml`：每日 GitHub Actions 排程

如果 ESPN 修改資料格式，請調整 `scripts/update_standings.py` 的解析方式；不會自動替換成不確定的資料。
