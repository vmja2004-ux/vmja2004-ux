const historyData = (window.CB_WEEKLY_HISTORY && window.CB_WEEKLY_HISTORY.length)
  ? window.CB_WEEKLY_HISTORY
  : [window.CB_WEEKLY_DATA].filter(Boolean);

let data = historyData[historyData.length - 1] || {};
let currentRows = [];

const tableLabels = {
  high_volume: "成交量大於 1000 張",
  top_gainers: "漲幅前十大",
  top_losers: "跌幅前十大",
  sellback_large: "賣回大於 100 張",
  new_listings: "近期掛牌",
  conversion_large: "轉換大於 100 張",
  auction_cases: "近期競拍",
  company_calls: "公司贖回風險",
  putback_within_3m: "三個月內賣回",
  maturity_within_3m: "三個月內到期",
};

const actionClass = {
  "Priority research": "priority",
  "Watch only": "watch",
  "Avoid / remove from watchlist": "avoid",
  "Event-driven only": "event",
};

function periodKey(item) {
  const period = item.report_period || {};
  return `${period.start || ""}_${period.end || ""}`;
}

function periodLabel(item) {
  const period = item.report_period || {};
  return `${period.start || ""} ~ ${period.end || ""}`;
}

function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "number") return value.toLocaleString("zh-TW");
  return value;
}

function csvEscape(value) {
  return `"${String(value ?? "").replaceAll('"', '""')}"`;
}

function initPeriodFilter() {
  const select = document.getElementById("periodFilter");
  select.innerHTML = historyData
    .map((item) => `<option value="${periodKey(item)}">${periodLabel(item)}</option>`)
    .join("");
  select.value = periodKey(data);
  select.addEventListener("change", () => {
    data = historyData.find((item) => periodKey(item) === select.value) || data;
    resetSignalFilter();
    renderAll();
  });
}

function initSummary() {
  const summary = data.summary || {};
  const metrics = [
    ["高成交量", summary.high_volume_count],
    ["新掛牌", summary.new_listings_count],
    ["高轉換量", summary.conversion_large_count],
    ["大額賣回", summary.sellback_large_count],
    ["贖回風險", summary.company_call_count],
  ];
  document.getElementById("summary").innerHTML =
    metrics
      .map(([label, value]) => `<article class="metric"><span>${label}</span><strong>${formatNumber(value)}</strong></article>`)
      .join("") +
    `<article class="metric wide"><span>市場解讀</span><strong>${summary.interpretation_zh || ""}</strong></article>`;
}

function initWarnings() {
  const warnings = data.warnings || [];
  const node = document.getElementById("warnings");
  node.innerHTML = warnings.length
    ? warnings.map((warning) => `<div class="warning-card"><strong>${warning.table}</strong>：${warning.message}</div>`).join("")
    : "";
}

function resetSignalFilter() {
  const select = document.getElementById("signalFilter");
  const previous = select.value;
  const signals = new Set();
  (data.watchlist || []).forEach((row) => {
    String(row.signal_type || "")
      .split("、")
      .filter(Boolean)
      .forEach((signal) => signals.add(signal));
  });
  select.innerHTML = `<option value="">全部訊號</option>` +
    [...signals].sort().map((signal) => `<option value="${signal}">${signal}</option>`).join("");
  if ([...signals].includes(previous)) select.value = previous;
}

function initFilters() {
  resetSignalFilter();
  ["search", "signalFilter", "riskFilter", "sortBy"].forEach((id) => {
    document.getElementById(id).addEventListener("input", renderWatchlist);
  });
  document.getElementById("exportCsv").addEventListener("click", exportCsv);
}

function sortValue(row, sortBy) {
  const raw = row.raw || {};
  if (sortBy === "volume") return raw.high_volume?.weekly_volume || 0;
  if (sortBy === "remaining") {
    const ratios = Object.values(raw)
      .map((item) => item.remaining_ratio_pct)
      .filter((value) => typeof value === "number");
    return ratios.length ? Math.min(...ratios) : 999;
  }
  if (sortBy === "listing") return Date.parse(raw.new_listings?.listing_date || raw.auction_cases?.listing_date || "1900-01-01");
  return row.score || 0;
}

function renderWatchlist() {
  const search = document.getElementById("search").value.trim().toLowerCase();
  const signal = document.getElementById("signalFilter").value;
  const risk = document.getElementById("riskFilter").value;
  const sortBy = document.getElementById("sortBy").value;

  currentRows = (data.watchlist || [])
    .filter((row) => !search || `${row.code} ${row.name}`.toLowerCase().includes(search))
    .filter((row) => !signal || String(row.signal_type).includes(signal))
    .filter((row) => !risk || row.risk_level === risk)
    .sort((a, b) => sortValue(b, sortBy) - sortValue(a, sortBy));

  document.getElementById("resultCount").textContent = `${currentRows.length} 檔`;
  document.getElementById("watchlistBody").innerHTML = currentRows
    .map((row, index) => {
      const badge = actionClass[row.suggested_action] || "watch";
      const riskClass = row.risk_level === "高" ? "risk-high" : row.risk_level === "中" ? "risk-mid" : "";
      return `<tr data-code="${row.code}">
        <td>${index + 1}</td>
        <td>${row.code}</td>
        <td>${row.name}</td>
        <td>${row.score}</td>
        <td>${row.signal_type}</td>
        <td class="${riskClass}">${row.risk_level}</td>
        <td><span class="badge ${badge}">${row.suggested_action}</span></td>
        <td>${row.trading_interpretation}</td>
      </tr>`;
    })
    .join("");
  document.querySelectorAll("#watchlistBody tr").forEach((row) => {
    row.addEventListener("click", () => openModal(row.dataset.code));
  });
}

function renderDetailTables() {
  const container = document.getElementById("detailTables");
  container.innerHTML = Object.entries(data.tables || {})
    .map(([key, rows]) => {
      const sample = rows[0] || {};
      const columns = Object.keys(sample).slice(0, 6);
      const body = rows
        .slice(0, 12)
        .map((row) => `<tr>${columns.map((column) => `<td>${formatNumber(row[column])}</td>`).join("")}</tr>`)
        .join("");
      return `<article class="table-card">
        <h2>${tableLabels[key] || key}</h2>
        <div class="mini-table">
          <table>
            <thead><tr>${columns.map((column) => `<th>${column}</th>`).join("")}</tr></thead>
            <tbody>${body}</tbody>
          </table>
        </div>
      </article>`;
    })
    .join("");
}

function barChart(containerId, items, options = {}) {
  const node = document.getElementById(containerId);
  const max = Math.max(...items.map((item) => item.value), 1);
  node.innerHTML = `<div class="bar-chart">
    ${items.map((item) => `
      <div class="bar-row">
        <span class="bar-label">${item.label}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${Math.max(3, item.value / max * 100)}%"></div></div>
        <span class="bar-value">${options.percent ? `${item.value}%` : formatNumber(item.value)}</span>
      </div>
    `).join("")}
  </div>`;
}

function renderSignalChart() {
  const tables = data.tables || {};
  const items = [
    ["轉換量", tables.conversion_large?.length || 0],
    ["新掛牌", tables.new_listings?.length || 0],
    ["賣回", tables.sellback_large?.length || 0],
    ["贖回", tables.company_calls?.length || 0],
    ["流動性", tables.high_volume?.length || 0],
    ["競拍", tables.auction_cases?.length || 0],
  ].map(([label, value]) => ({ label, value }));
  barChart("signalChart", items);
}

function renderScoreChart() {
  const items = (data.watchlist || [])
    .slice(0, 10)
    .map((row) => ({ label: `${row.code} ${row.name}`, value: row.score || 0 }));
  barChart("scoreChart", items);
}

function renderConversionChart() {
  const rows = (data.tables?.conversion_large || []).slice(0, 12);
  const maxVolume = Math.max(...rows.map((row) => row.weekly_conversion_volume || 0), 1);
  const maxIntensity = Math.max(...rows.map((row) => row.conversion_intensity_pct || 0), 1);
  const width = 640;
  const height = 280;
  const points = rows.map((row, index) => {
    const x = 52 + ((row.weekly_conversion_volume || 0) / maxVolume) * 520;
    const y = 230 - ((row.conversion_intensity_pct || 0) / maxIntensity) * 180;
    return { ...row, index, x, y };
  });
  document.getElementById("conversionChart").innerHTML = `
    <svg class="svg-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="轉換量與轉換強度散點圖">
      <line x1="46" y1="230" x2="585" y2="230" />
      <line x1="46" y1="38" x2="46" y2="230" />
      <text x="46" y="258">轉換量</text>
      <text x="12" y="34">強度</text>
      ${points.map((point) => `
        <g>
          <circle cx="${point.x}" cy="${point.y}" r="7" />
          <text x="${point.x + 10}" y="${point.y + 4}">${point.code}</text>
        </g>
      `).join("")}
    </svg>`;
}

function renderTrendChart() {
  const items = historyData.map((item) => ({
    label: (item.report_period?.end || "").slice(5),
    conversion: item.summary?.conversion_large_count || 0,
    listing: item.summary?.new_listings_count || 0,
    risk: item.summary?.company_call_count || 0,
  }));
  const max = Math.max(...items.flatMap((item) => [item.conversion, item.listing, item.risk]), 1);
  document.getElementById("trendChart").innerHTML = `
    <div class="trend-chart">
      ${items.map((item) => `
        <div class="trend-group">
          <div class="trend-bars">
            <span title="高轉換量" style="height:${Math.max(4, item.conversion / max * 100)}%"></span>
            <span title="新掛牌" style="height:${Math.max(4, item.listing / max * 100)}%"></span>
            <span title="贖回風險" style="height:${Math.max(4, item.risk / max * 100)}%"></span>
          </div>
          <small>${item.label}</small>
        </div>
      `).join("")}
    </div>
    <div class="legend"><span class="dot conversion"></span>高轉換量 <span class="dot listing"></span>新掛牌 <span class="dot risk"></span>贖回風險</div>`;
}

function renderCharts() {
  renderSignalChart();
  renderScoreChart();
  renderConversionChart();
  renderTrendChart();
}

function openModal(code) {
  const row = (data.watchlist || []).find((item) => item.code === code);
  if (!row) return;
  document.getElementById("modalCode").textContent = row.code;
  document.getElementById("modalTitle").textContent = row.name;
  document.getElementById("modalContent").innerHTML = `
    <p><strong>分數：</strong>${row.score}</p>
    <p><strong>訊號：</strong>${row.signal_type}</p>
    <p><strong>建議動作：</strong>${row.suggested_action}</p>
    <p><strong>交易解讀：</strong>${row.trading_interpretation}</p>
    <p><strong>風險提醒：</strong>${row.risk_warning}</p>
    <div class="raw-block">${JSON.stringify(row.raw, null, 2)}</div>
  `;
  document.getElementById("detailModal").showModal();
}

function exportCsv() {
  const header = ["rank", "code", "name", "score", "signal_type", "risk_level", "suggested_action", "trading_interpretation", "risk_warning"];
  const lines = [header.join(",")].concat(
    currentRows.map((row, index) =>
      header
        .map((key) => csvEscape(key === "rank" ? index + 1 : row[key]))
        .join(",")
    )
  );
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `cbas_priority_watchlist_${periodKey(data)}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function renderAll() {
  initSummary();
  initWarnings();
  renderCharts();
  renderWatchlist();
  renderDetailTables();
}

document.getElementById("closeModal").addEventListener("click", () => document.getElementById("detailModal").close());
initPeriodFilter();
initFilters();
renderAll();
