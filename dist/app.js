const data = window.CBAS_DATA || {
  generated_at: "",
  latest_source_date: "",
  source_files: [],
  summary: {},
  quotes: [],
  primary_market: [],
  events: [],
  warnings: [],
};

function unpackDataset(dataset) {
  if (Array.isArray(dataset)) return dataset;
  if (!dataset?.columns || !dataset?.rows) return [];
  return dataset.rows.map((row) => Object.fromEntries(dataset.columns.map((column, index) => [column, row[index]])));
}

const quoteRows = unpackDataset(data.quotes);
const primaryRows = unpackDataset(data.primary_market);
const eventRows = unpackDataset(data.events);

function sourceName(sourceId) {
  const source = (data.source_files || [])[sourceId];
  return source?.name || "";
}

const views = {
  quotes: {
    title: "券商報價",
    eyebrow: "Quotes",
    rows: () => quoteRows,
    columns: [
      ["cb_code", "CB 代碼"],
      ["cb_name", "名稱"],
      ["premium_per_100", "百元權利金"],
      ["premium_reference", "參考權利金"],
      ["cb_price", "CB 價"],
      ["parity", "轉換價值"],
      ["premium_ratio", "折溢價"],
      ["option_expiration", "選擇權到期"],
      ["put_date", "賣回日"],
      ["source_id", "來源"],
    ],
  },
  primary_market: {
    title: "初級市場",
    eyebrow: "Primary",
    rows: () => primaryRows,
    columns: [
      ["cb_code", "CB 代碼"],
      ["cb_name", "名稱"],
      ["issue_type", "類型"],
      ["issue_amount_100m", "發行量（億）"],
      ["tcri_or_guarantor", "TCRI／擔保"],
      ["lead_underwriter", "主辦券商"],
      ["bookbuilding_period", "詢圈／投標"],
      ["listing_date", "掛牌日"],
      ["op_effective_date", "OP 生效日"],
      ["source_id", "來源"],
    ],
  },
  events: {
    title: "到期／贖回提醒",
    eyebrow: "Events",
    rows: () => eventRows,
    columns: [
      ["stock_code", "股票代碼"],
      ["cb_code", "CB 代碼"],
      ["name", "名稱"],
      ["event_type", "狀態"],
      ["redeem_date", "贖回／終止日"],
      ["next_put_date", "賣回日"],
      ["maturity_date", "到期日"],
      ["source_id", "來源"],
    ],
  },
};

function $(id) {
  return document.getElementById(id);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatNumber(value, key = "") {
  if (value === null || value === undefined || value === "") return "";
  if (key === "source_id") return escapeHtml(sourceName(value));
  if (typeof value !== "number") return escapeHtml(value);
  if (key.includes("ratio") || key.includes("rate")) return `${(value * 100).toFixed(1)}%`;
  return value.toLocaleString("zh-TW", { maximumFractionDigits: 3 });
}

function formatDateTime(value) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("zh-TW", { hour12: false });
}

function renderHeader() {
  $("subtitle").textContent = `最新來源日期 ${data.latest_source_date || "-"}，更新時間 ${formatDateTime(data.generated_at) || "-"}`;
}

function renderMetrics() {
  const summary = data.summary || {};
  const rows = [
    ["報價標的", summary.quote_count || 0],
    ["發行案件", summary.primary_market_count || 0],
    ["事件提醒", summary.event_count || 0],
    ["納入檔案", summary.included_files || 0],
    ["來源日期", data.latest_source_date || "-"],
  ];
  $("metrics").innerHTML = rows
    .map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${formatNumber(value)}</strong></div>`)
    .join("");
}

function renderSources() {
  $("sourceRows").innerHTML = (data.source_files || [])
    .map((file) => `<div class="source-row ${file.included ? "" : "muted"}">
      <div>
        <strong>${escapeHtml(file.name)}</strong>
        <span>${escapeHtml(file.source_date || "")}</span>
      </div>
      <small>${file.included ? "已納入" : "未納入"}</small>
    </div>`)
    .join("");
  $("warningRows").innerHTML = (data.warnings || [])
    .map((warning) => `<div class="warning-row">
      <strong>${escapeHtml(warning.source_file || "來源警示")}</strong>
      <span>${escapeHtml(warning.message || "")}</span>
    </div>`)
    .join("");
}

function renderWatchlist() {
  const issueCodes = new Set(primaryRows.map((row) => row.cb_code));
  const eventStockCodes = new Set(eventRows.map((row) => row.stock_code));
  const rows = quoteRows
    .map((quote) => {
      let score = 0;
      if (quote.premium_per_100 !== undefined) score += 25;
      if (quote.option_expiration) score += 15;
      if (issueCodes.has(quote.cb_code)) score += 20;
      if (eventStockCodes.has(quote.stock_code)) score += 20;
      if (quote.premium_ratio !== undefined && quote.premium_ratio < 0.2) score += 15;
      return { ...quote, score: Math.min(score, 100) };
    })
    .sort((a, b) => (b.score || 0) - (a.score || 0))
    .slice(0, 12);
  $("watchlistCount").textContent = `${rows.length} 筆`;
  $("watchlistRows").innerHTML = rows
    .map((row) => `<button class="watch-row" type="button" data-code="${escapeHtml(row.cb_code)}">
      <span class="score">${formatNumber(row.score)}</span>
      <span>
        <strong>${escapeHtml(row.cb_code)} ${escapeHtml(row.cb_name || "")}</strong>
        <small>權利金 ${formatNumber(row.premium_per_100)}，到期 ${escapeHtml(row.option_expiration || "-")}</small>
      </span>
    </button>`)
    .join("");
  document.querySelectorAll(".watch-row").forEach((button) => {
    button.addEventListener("click", () => {
      $("viewSelect").value = "quotes";
      $("searchInput").value = button.dataset.code;
      renderTable();
      document.querySelector(".table-section").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

function initFilters() {
  const sources = [...new Set((data.source_files || []).map((file) => file.name))].sort();
  $("sourceSelect").innerHTML =
    `<option value="">全部來源</option>` + sources.map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("");
  ["searchInput", "viewSelect", "sourceSelect", "sortSelect"].forEach((id) => {
    $(id).addEventListener("input", renderTable);
  });
  $("downloadJson").addEventListener("click", () => downloadFile(`cbas-${data.latest_source_date || "latest"}.json`, JSON.stringify(data, null, 2), "application/json"));
  $("downloadCsv").addEventListener("click", downloadCurrentCsv);
}

function currentRows() {
  const view = views[$("viewSelect").value];
  const search = $("searchInput").value.trim().toLowerCase();
  const source = $("sourceSelect").value;
  const sort = $("sortSelect").value;
  const searchable = (row) => Object.values(row).join(" ").toLowerCase();
  const rows = view
    .rows()
    .filter((row) => !source || sourceName(row.source_id) === source)
    .filter((row) => !search || searchable(row).includes(search));
  rows.sort((a, b) => {
    if (sort === "premium") return (b.premium_per_100 || b.premium_reference || 0) - (a.premium_per_100 || a.premium_reference || 0);
    if (sort === "date") return String(b.option_expiration || b.listing_date || b.redeem_date || "").localeCompare(String(a.option_expiration || a.listing_date || a.redeem_date || ""));
    if (sort === "score") return (b.score || 0) - (a.score || 0);
    return String(a.cb_code || a.stock_code || "").localeCompare(String(b.cb_code || b.stock_code || ""));
  });
  return rows;
}

function renderTable() {
  const view = views[$("viewSelect").value];
  const rows = currentRows();
  $("tableTitle").textContent = view.title;
  $("tableEyebrow").textContent = view.eyebrow;
  $("rowCount").textContent = `${rows.length} 筆`;
  $("tableHead").innerHTML = `<tr>${view.columns.map(([, label]) => `<th>${label}</th>`).join("")}</tr>`;
  $("tableBody").innerHTML = rows.length
    ? rows
        .map((row) => `<tr>${view.columns.map(([key]) => `<td>${formatNumber(row[key], key)}</td>`).join("")}</tr>`)
        .join("")
    : `<tr><td colspan="${view.columns.length}" class="empty">沒有符合條件的資料</td></tr>`;
}

function downloadFile(filename, content, type) {
  const blob = new Blob([content], { type: `${type};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function downloadCurrentCsv() {
  const view = views[$("viewSelect").value];
  const rows = currentRows();
  const csvRows = [view.columns.map(([, label]) => label)];
  rows.forEach((row) => {
    csvRows.push(view.columns.map(([key]) => String(row[key] ?? "").replaceAll('"', '""')));
  });
  const csv = csvRows.map((row) => row.map((cell) => `"${cell}"`).join(",")).join("\n");
  downloadFile(`cbas-${$("viewSelect").value}-${data.latest_source_date || "latest"}.csv`, csv, "text/csv");
}

function renderAll() {
  renderHeader();
  renderMetrics();
  renderSources();
  renderWatchlist();
  initFilters();
  renderTable();
}

renderAll();
