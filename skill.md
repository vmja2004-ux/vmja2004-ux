# Yuanta CB Weekly Update Skill

## When to use
Use this skill when the user asks to update, parse, analyze, or refresh the Yuanta Convertible Bond weekly market review dashboard.

Trigger phrases include:
- 更新本週元大CB週評
- 更新可轉債儀表板
- 解析最新元大CB PDF
- 產生本週CBAS追蹤名單

## Goal
Parse the newest Yuanta CB weekly PDF in `/data/raw/`, update processed data, recalculate CBAS watchlist, refresh the dashboard, run tests, and report results in Traditional Chinese.

## Steps
1. Read `AGENTS.md`.
2. Find the newest PDF in `/data/raw/`.
3. Parse these 10 sections:
   - 可轉債成交張數大於1000張
   - 漲幅前十大CB
   - 跌幅前十大CB
   - CB賣回張數大於100張
   - 近期掛牌CB
   - CB轉換張數大於100張
   - 近期競拍CB案件
   - 近期公司執行贖回權的CB
   - 三個月內賣回的CB
   - 三個月內到期的CB
4. Generate:
   - `/data/processed/cb_weekly_latest.json`
   - `/data/processed/cb_weekly_latest.csv`
   - `/data/history/{report_period}.json`
5. Recalculate CBAS watchlist score.
6. Update dashboard UI if needed.
7. Run:
   - `npm run update:weekly`
   - `npm run test`
   - `npm run build`
8. Report:
   - 本週資料期間
   - 成功解析表格數
   - 解析警告
   - 前10名追蹤標的
   - 儀表板啟動方式
   - 下一步建議

## Trading rules
Prioritize:
1. CB轉換張數
2. 近期掛牌CB
3. 賣回張數
4. 贖回風險
5. 成交量流動性
6. 競拍案件
7. 三個月內賣回
8. 三個月內到期
9. 漲跌幅

Do not treat weekly gainers as direct buy signals.

Use Traditional Chinese for all user-facing output.
Avoid definitive buy/sell language. Use:
- 優先研究
- 觀察
- 移出追蹤
- 事件型交易
- 高風險，不適合一般追價