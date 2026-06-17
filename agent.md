# AGENTS.md

## Project Name

Yuanta CB Weekly Interactive Dashboard

## Mission

Build and maintain an interactive web dashboard that converts the weekly Yuanta Convertible Bond Market Review PDF into structured data, visual insights, and CB/CBAS trading watchlists.

The dashboard must help the user answer one question:

> Which convertible bonds deserve attention this week, and why?

## Primary User

The user is an active Taiwan CB / CBAS trader.
They need fast weekly interpretation, not just raw tables.

## Core Trading Logic

Prioritize signals in this order:

1. CB conversion volume
2. Newly listed CBs
3. Put-back / sell-back volume
4. Company call / redemption risk
5. Trading volume and liquidity
6. Recent auction cases
7. CBs within 3 months of put-back
8. CBs within 3 months of maturity
9. Weekly gainers / losers

Do not over-emphasize price gain/loss rankings. They are momentum references, not direct buy signals.

## Required Dashboard Sections

### 1. Weekly Market Summary

Show:

* Report date range
* Number of high-volume CBs
* Number of newly listed CBs
* Number of CBs with large conversion volume
* Number of CBs with large sell-back volume
* Number of CBs under company call / redemption risk
* Auto-generated short market interpretation in Traditional Chinese

### 2. CBAS Priority Watchlist

Generate a ranked table with score from 0 to 100.

Suggested scoring:

* Conversion activity: 40%
* Newly listed / recently auctioned: 25%
* Liquidity: 15%
* Redemption / maturity / sell-back risk penalty: -20%
* Momentum reference: 10%

Each row must include:

* CB code
* CB name
* Score
* Signal type
* Trading interpretation
* Risk warning
* Suggested action:

  * Priority research
  * Watch only
  * Avoid / remove from watchlist
  * Event-driven only

### 3. Conversion Signal Table

Focus on weekly conversion volume.

Calculate:

* Weekly conversion volume
* Remaining ratio
* Conversion intensity if possible:
  weekly converted volume / previous week outstanding volume

Flag:

* > 10% = Watch
* > 20% = Warning
* > 30% = Late-stage / possible exit pressure

### 4. Newly Listed CB Table

Show:

* CB code
* Name
* Listing date
* Issue price
* Conversion price
* Decomposition date
* Underwriting method
* TCRI / guarantee bank

Flag:

* Issue price >130% = Hot auction / beware listing selling pressure
* Issue price 100–105% = Possible underpriced or low-demand case
* Decomposition date within next 7 days = actionable watch

### 5. Sell-back / Put-back Risk Table

Show:

* CB code
* Name
* Put-back date if available
* Current outstanding volume
* Remaining ratio
* Weekly sell-back volume

Flag:

* Remaining ratio <10% = mostly exited
* Large weekly sell-back = market rejection signal

### 6. Company Call / Redemption Risk Table

Show:

* CB code
* Name
* Outstanding volume
* Remaining ratio
* Termination date

Flag:

* Remaining ratio <5% = remove from normal trading watchlist
* Termination date within 14 days = high risk

### 7. Liquidity Table

From the high-volume CB list.

Show:

* Ranking
* CB code
* Name
* Weekly trading volume
* Estimated average daily volume

Flag:

* Avg daily volume <30 = avoid
* Avg daily volume 30–100 = low liquidity
* Avg daily volume >100 = tradable
* Avg daily volume >300 = preferred liquidity

### 8. Detail Page / Modal

For each CB, provide:

* All available report fields
* Signal tags
* Score breakdown
* Plain-language explanation in Traditional Chinese

## Data Pipeline Requirements

Expected input:

* Weekly Yuanta CB market review PDF placed in `/data/raw/`
* File naming convention:
  `yuanta_cb_weekly_YYYYMMDD_YYYYMMDD.pdf`

Required output:

* `/data/processed/cb_weekly_latest.json`
* `/data/processed/cb_weekly_latest.csv`
* `/data/history/YYYYMMDD_YYYYMMDD.json`
* Static web dashboard in `/dist/` or app source in `/src/`

## PDF Parsing Rules

The PDF usually contains these sections:

1. 可轉債成交張數大於1000張
2. 漲幅前十大CB
3. 跌幅前十大CB
4. CB賣回張數大於100張
5. 近期掛牌CB
6. CB轉換張數大於100張
7. 近期競拍CB案件
8. 近期公司執行贖回權的CB
9. 三個月內賣回的CB
10. 三個月內到期的CB

Use robust parsing:

* Prefer table extraction if possible.
* Fall back to PDF text parsing.
* Preserve Traditional Chinese column names internally, but expose normalized English keys in JSON.
* Do not silently drop rows.
* If parsing confidence is low, create a warning in the dashboard.

## Suggested Normalized JSON Schema

{
"report_period": {
"start": "YYYY-MM-DD",
"end": "YYYY-MM-DD"
},
"source_file": "",
"generated_at": "",
"tables": {
"high_volume": [],
"top_gainers": [],
"top_losers": [],
"sellback_large": [],
"new_listings": [],
"conversion_large": [],
"auction_cases": [],
"company_calls": [],
"putback_within_3m": [],
"maturity_within_3m": []
},
"watchlist": [],
"warnings": []
}

## UI Requirements

Use a clean dashboard style.

Required interactions:

* Search by CB code or name
* Filter by signal type
* Filter by risk level
* Sort by score, volume, remaining ratio, listing date
* Click row to open detail modal
* Export current filtered table as CSV
* Responsive layout for desktop and tablet

Preferred stack:

* Vite
* React
* TypeScript
* Tailwind CSS
* Recharts or lightweight chart library
* Python parser scripts for PDF extraction

If the repository already has a different stack, follow the existing stack.

## Visual Design

Use a professional financial dashboard style:

* White or dark neutral background
* Signal badges:

  * Green: Priority research
  * Yellow: Watch
  * Red: Risk / avoid
  * Blue: Event-driven
* Avoid decorative design.
* Optimize for fast weekly decision-making.

## Automation Requirements

Add a repeatable command:

```bash
npm run update:weekly
```

This command should:

1. Find the newest PDF in `/data/raw/`
2. Parse all tables
3. Generate JSON and CSV
4. Recalculate scores
5. Build or refresh the dashboard
6. Run tests
7. Print a concise update summary

Also add:

```bash
npm run dev
npm run build
npm run test
```

## Testing Requirements

Create tests for:

* PDF parser can identify all 10 sections
* Date range is extracted correctly
* Watchlist scoring works
* Risk flags work
* Empty or malformed PDF produces visible warnings instead of crashing

## Weekly Operating Procedure

When the user provides a new PDF:

1. Save it to `/data/raw/`
2. Run `npm run update:weekly`
3. Inspect parsing warnings
4. Open dashboard locally
5. Verify top watchlist
6. Commit processed data and app changes

## Coding Style

* TypeScript strict mode
* Small functions
* Clear data types
* No hardcoded weekly dates
* No hardcoded CB names unless used only in tests
* Keep trading rules configurable in `/config/scoring.ts` or `/config/scoring.json`

## Important Trading Interpretation Rules

Use Traditional Chinese for all user-facing explanations.

Do not say “buy” or “sell” as a definitive recommendation.
Use:

* 優先研究
* 觀察
* 移出追蹤
* 事件型交易
* 高風險，不適合一般追價

Always explain why a CB is ranked.

Examples:

* 「本週轉換張數大，代表市場正在快速轉股，可能進入收割或末升段。」
* 「發行價高於130%，代表競拍熱度高，但掛牌後需留意套利賣壓。」
* 「剩餘比率低於5%，代表流通籌碼接近結束，不適合作為一般波段標的。」
* 「成交量高代表流動性足夠，但不是買進訊號。」

## Final Response Format for Codex Tasks

When finishing a task, report:

1. What changed
2. How to run it
3. Parsing confidence
4. Known limitations
5. Next recommended improvement
