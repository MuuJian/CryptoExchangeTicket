const state = {
  records: [],
  breakouts: [],
  scanStatus: {},
  sortKey: "symbol",
  sortDir: "asc",
  breakoutSortKey: "date",
  breakoutSortDir: "desc",
};

const elements = {
  scanStatus: document.getElementById("scan-status"),
  statCount: document.getElementById("stat-count"),
  statUpdated: document.getElementById("stat-updated"),
  recordsBody: document.getElementById("rows"),
  breakoutsBody: document.getElementById("breakout-rows"),
  search: document.getElementById("search"),
  limit: document.getElementById("limit"),
  refresh: document.getElementById("refresh"),
  breakoutSearch: document.getElementById("breakout-search"),
  breakoutType: document.getElementById("breakout-type"),
  breakoutRefresh: document.getElementById("breakout-refresh"),
};

const recordsTable = createKeyedTable({
  tbody: elements.recordsBody,
  colspan: 5,
  getKey: row => row.symbol,
  createRow: createRecordRow,
  updateRow: updateRecordRow,
});

const breakoutsTable = createKeyedTable({
  tbody: elements.breakoutsBody,
  colspan: 5,
  getKey: row => `${row.date || ""}:${row.symbol || ""}:${row.breakout_type || ""}:${row.price || ""}`,
  createRow: createBreakoutRow,
  updateRow: updateBreakoutRow,
});

async function loadStatus() {
  try {
    const resp = await fetch("/api/status");
    state.scanStatus = await resp.json();
    elements.scanStatus.textContent = "后台扫描状态：" + describeStatus(state.scanStatus);
  } catch {
    elements.scanStatus.textContent = "后台扫描状态：读取失败";
  }
}

function describeStatus(status) {
  if (status.running) {
    return `扫描中，从 ${cleanDate(status.started_at)} 开始`;
  }
  if (status.finished_at) {
    const message = `上次完成 ${cleanDate(status.finished_at)}，下次 ${cleanDate(status.next_scan_at)}`;
    return status.warning ? `${message}；${status.warning}` : message;
  }
  if (status.error) {
    return `错误：${status.error}`;
  }
  return status.auto_scan ? "等待第一次扫描" : "自动扫描已关闭";
}

async function loadData() {
  recordsTable.render([], "Loading...");
  try {
    const resp = await fetch("/api/ath-atl");
    const data = await resp.json();
    state.records = data.records || [];
    renderRecords();
  } catch {
    recordsTable.render([], "Failed to load ATH/ATL data", "error");
  }
}

async function loadBreakouts() {
  breakoutsTable.render([], "Loading...");
  try {
    const resp = await fetch("/api/breakouts");
    const data = await resp.json();
    state.breakouts = data.breakouts || [];
    renderBreakouts();
  } catch {
    breakoutsTable.render([], "Failed to load breakout data", "error");
  }
}

function renderRecords() {
  const search = elements.search.value.trim().toUpperCase();
  const limit = Number(elements.limit.value);

  const filtered = state.records
    .filter(row => !search || row.symbol.includes(search))
    .sort((a, b) => compareValues(a[state.sortKey], b[state.sortKey]) * sortMultiplier(state.sortDir));

  const shown = limit > 0 ? filtered.slice(0, limit) : filtered;

  elements.statCount.textContent = filtered.length.toLocaleString();
  elements.statUpdated.textContent = cleanDate(state.records[0]?.updated_at);

  const emptyMessage = state.scanStatus.running
    ? "后台正在扫描，数据会自动出现。第一次全量历史 K 线会慢一点。"
    : "没有数据。后台会自动扫描，也可以手动运行 python3 -m ath_atl.tracker";
  recordsTable.render(shown, emptyMessage);
}

function renderBreakouts() {
  const search = elements.breakoutSearch.value.trim().toUpperCase();
  const type = elements.breakoutType.value;

  const filtered = state.breakouts
    .filter(row => {
      const textMatch = !search || row.symbol.includes(search);
      const typeMatch = !type || row.breakout_type === type;
      return textMatch && typeMatch;
    })
    .sort((a, b) => compareValues(a[state.breakoutSortKey], b[state.breakoutSortKey]) * sortMultiplier(state.breakoutSortDir));

  const emptyMessage = state.scanStatus.running
    ? "后台正在扫描；如果有新高/新低，会自动出现在这里。"
    : "没有突破数据。后台会自动扫描，也可以手动运行 python3 -m ath_atl.tracker";
  breakoutsTable.render(filtered, emptyMessage);
}

function createRecordRow() {
  const tr = document.createElement("tr");
  const { cell: symbol, link: symbolLink } = symbolLinkCell();
  const currentPrice = cell("td", "num");
  const athPrice = cell("td", "num high");
  const atlPrice = cell("td", "num low");
  const updated = cell("td", "muted");
  tr.append(symbol, currentPrice, athPrice, atlPrice, updated);
  tr._cells = { symbolLink, currentPrice, athPrice, atlPrice, updated };
  return tr;
}

function updateRecordRow(tr, row) {
  updateSymbolLink(tr._cells.symbolLink, row);
  tr._cells.currentPrice.textContent = formatPrice(row.current_price);
  tr._cells.athPrice.textContent = formatPrice(row.ath_price);
  tr._cells.atlPrice.textContent = formatPrice(row.atl_price);
  tr._cells.updated.textContent = cleanDate(row.updated_at);
}

function createBreakoutRow() {
  const tr = document.createElement("tr");
  const date = cell("td");
  const { cell: symbol, link: symbolLink } = symbolLinkCell();
  const type = cell("td");
  const price = cell("td", "num");
  const previousPrice = cell("td", "num muted");
  tr.append(date, symbol, type, price, previousPrice);
  tr._cells = { date, symbolLink, type, price, previousPrice };
  return tr;
}

function updateBreakoutRow(tr, row) {
  const typeLabel = row.breakout_type === "new_high" ? "New high" : "New low";
  const typeClass = row.breakout_type === "new_high" ? "high" : "low";

  tr._cells.date.textContent = row.date || "-";
  updateSymbolLink(tr._cells.symbolLink, row);
  tr._cells.type.className = typeClass;
  tr._cells.type.textContent = typeLabel;
  tr._cells.price.textContent = formatPrice(row.price);
  tr._cells.previousPrice.textContent = formatPrice(row.previous_price);
}

function createKeyedTable({ tbody, colspan, getKey, createRow, updateRow }) {
  const rowsByKey = new Map();

  function render(rows, emptyMessage, emptyClass = "") {
    if (!rows.length) {
      rowsByKey.clear();
      tbody.replaceChildren(createEmptyRow(colspan, emptyMessage, emptyClass));
      return;
    }

    const fragment = document.createDocumentFragment();
    const nextKeys = new Set();

    for (const row of rows) {
      const key = getKey(row);
      nextKeys.add(key);

      let tr = rowsByKey.get(key);
      if (!tr) {
        tr = createRow(row);
        rowsByKey.set(key, tr);
      }
      updateRow(tr, row);
      fragment.append(tr);
    }

    for (const [key, tr] of rowsByKey.entries()) {
      if (!nextKeys.has(key)) {
        tr.remove();
        rowsByKey.delete(key);
      }
    }

    tbody.replaceChildren(fragment);
  }

  return { render };
}

function createEmptyRow(colspan, message, extraClass = "") {
  const tr = document.createElement("tr");
  const td = document.createElement("td");
  td.className = ["empty", extraClass].filter(Boolean).join(" ");
  td.colSpan = colspan;
  td.textContent = message;
  tr.append(td);
  return tr;
}

function cell(tagName, className = "") {
  const node = document.createElement(tagName);
  if (className) node.className = className;
  return node;
}

function symbolLinkCell() {
  const symbol = cell("td", "symbol");
  const link = document.createElement("a");
  link.className = "symbol-link";
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  symbol.append(link);
  return { cell: symbol, link };
}

function updateSymbolLink(link, row) {
  link.href = tradingViewUrl(row);
  link.textContent = row.symbol || "-";
}

function tradingViewUrl(row) {
  const suffix = row.market_type === "futures" ? ".P" : "";
  const tvSymbol = `BINANCE:${row.symbol}${suffix}`;
  return `https://www.tradingview.com/chart/n6rCV2e0/?symbol=${encodeURIComponent(tvSymbol)}`;
}

function formatPrice(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  const number = Number(value);
  if (number === 0) return "$0";
  if (Math.abs(number) >= 1) return "$" + number.toLocaleString(undefined, { maximumFractionDigits: 8 });
  return "$" + number.toPrecision(6).replace(/0+$/, "").replace(/\.$/, "");
}

function cleanDate(value) {
  if (!value) return "-";
  const text = String(value);
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;

  const normalized = text.includes("T") ? text : text.replace(" ", "T");
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(normalized);
  const date = new Date(hasTimezone ? normalized : normalized + "Z");
  if (Number.isNaN(date.getTime())) return text.slice(0, 19).replace("T", " ");

  const parts = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(date).reduce((acc, part) => {
    acc[part.type] = part.value;
    return acc;
  }, {});

  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second}`;
}

function compareValues(left, right) {
  const leftNum = Number(left);
  const rightNum = Number(right);
  if (!Number.isNaN(leftNum) && !Number.isNaN(rightNum)) return leftNum - rightNum;
  return String(left ?? "").localeCompare(String(right ?? ""));
}

function sortMultiplier(direction) {
  return direction === "asc" ? 1 : -1;
}

document.querySelectorAll("th[data-key]").forEach(th => {
  th.addEventListener("click", () => {
    const key = th.dataset.key;
    if (state.sortKey === key) {
      state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
    } else {
      state.sortKey = key;
      state.sortDir = "asc";
    }
    renderRecords();
  });
});

document.querySelectorAll("th[data-home-breakout-key]").forEach(th => {
  th.addEventListener("click", () => {
    const key = th.dataset.homeBreakoutKey;
    if (state.breakoutSortKey === key) {
      state.breakoutSortDir = state.breakoutSortDir === "asc" ? "desc" : "asc";
    } else {
      state.breakoutSortKey = key;
      state.breakoutSortDir = "asc";
    }
    renderBreakouts();
  });
});

elements.search.addEventListener("input", renderRecords);
elements.limit.addEventListener("change", renderRecords);
elements.refresh.addEventListener("click", loadData);
elements.breakoutSearch.addEventListener("input", renderBreakouts);
elements.breakoutType.addEventListener("change", renderBreakouts);
elements.breakoutRefresh.addEventListener("click", loadBreakouts);

loadStatus();
loadBreakouts();
loadData();
setInterval(loadStatus, 5000);
setInterval(loadBreakouts, 30000);
setInterval(loadData, 30000);
