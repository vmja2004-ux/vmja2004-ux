const data = window.CB_WEEKLY_DATA || {};
let currentRows = [];

const tableLabels = {
  high_volume: "可轉債成交張數大於 1000 張",
  top_gainers: "漲幅前十大 CB",
  top_losers: "跌幅前十大 CB",
  sellback_large: "CB 賣回張數大於 100 張",
  new_listings: "近期掛牌 CB",
  conversion_large: "CB 轉換張數大於 100 張",
  auction_cases: "近期競拍 CB 案件",
  company_calls: "近期公司執行贖回權的 CB",
  putback_within_3m: "三個月內賣回的 CB",
  maturity_within_3m: "三個月內到期的 CB",
};

const actionClass = {
  "Priority research": "priority",
  "Watch only": "watch",
  "Avoid / remove from watchlist": "avoid",
  "Event-driven only": "event",
};

function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "number") return value.toLocaleString("zh-TW");
  return value;
}

function csvEscape(value) {
  return `"${String(value ?? "").replaceAll('"', '""')}"`;
}

function initSummary() {
  const period = data.report_period || {};
  document.getElementById("period").textContent = `${period.start || ""} ~ ${period.end || ""}`;
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
    `<article class="metric wide"><span>市場解讀</span><strong style="font-size:16px;line-height:1.7">${summary.interpretation_zh || ""}</strong></article>`;
}

function initWarnings() {
  const warnings = data.warnings || [];
  const node = document.getElementById("warnings");
  if (!warnings.length) {
    node.innerHTML = "";
    return;
  }
  node.innerHTML = warnings
    .map((warning) => `<div class="warning-card"><strong>${warning.table}</strong>：${warning.message}</div>`)
    .join("");
}

function initFilters() {
  const signals = new Set();
  (data.watchlist || []).forEach((row) => {
    String(row.signal_type || "")
      .split("、")
      .filter(Boolean)
      .forEach((signal) => signals.add(signal));
  });
  const select = document.getElementById("signalFilter");
  [...signals].sort().forEach((signal) => {
    const option = document.createElement("option");
    option.value = signal;
    option.textContent = signal;
    select.appendChild(option);
  });
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
  link.download = "cbas_priority_watchlist.csv";
  link.click();
  URL.revokeObjectURL(url);
}

document.getElementById("closeModal").addEventListener("click", () => document.getElementById("detailModal").close());
initSummary();
initWarnings();
initFilters();
renderWatchlist();
renderDetailTables();
