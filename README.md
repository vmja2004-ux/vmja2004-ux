# CBAS 報價及發行資訊

這個專案把 `CBAS報價及發行資訊` 資料夾中的 Excel 檔整理成靜態查詢網頁，方便在 GitHub Pages 上查詢：

- 券商 CBAS 報價
- 初級市場與發行案件
- 到期、賣回、強制贖回提醒
- 來源檔案狀態與未納入警示

## 資料來源

本機預設讀取：

```powershell
C:\Users\vmja2\Downloads\01_投資交易_CB_選擇權\CBAS報價及發行資訊
```

GitHub Actions 無法讀取本機 `Downloads`，因此原始 `.xlsx` 只保留在本機，不提交到 GitHub。同步時會暫時複製到：

```powershell
data\source\cbas
```

## 手動更新

```powershell
python scripts\update_cbas.py
python scripts\test_cbas.py
```

如要指定來源資料夾：

```powershell
$env:CBAS_SOURCE_DIR="data\source\cbas"
python scripts\update_cbas.py
python scripts\test_cbas.py
```

## 每週同步並推送

```powershell
powershell -ExecutionPolicy Bypass -File scripts\update_cbas_and_push.ps1
```

這支腳本會複製本機下載資料夾最新 `.xlsx`，重建網頁資料，提交並推送到 GitHub。推送後 GitHub Pages 會重新部署。

## GitHub Pages

`.github/workflows/cbas-weekly.yml` 會在推送到 `main` 後驗證已產生的資料並部署 `dist`。若要讓 GitHub Pages 反映本機最新下載資料，請先執行每週同步並推送腳本。每週排程會重新部署目前 repo 內已整理好的資料，但不會讀取本機新下載檔。

## 產出檔案

- `data/processed/cbas_latest.json`
- `data/history/cbas/YYYYMMDD.json`
- `dist/data/cbas-latest.js`
- `dist/index.html`

## 注意事項

目前 `.xlsx` 已可自動納入。舊版 `.xls` 檔需要 `xlrd` 或先轉成 `.xlsx`，目前會在網頁上列為來源警示，不會靜默忽略。
