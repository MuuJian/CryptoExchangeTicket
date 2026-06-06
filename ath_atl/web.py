import argparse
import json
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    from .tracker import (
        ATHATLStore,
        ATHATLTracker,
        BinanceClient,
        DEFAULT_BREAKOUTS_PATH,
        DEFAULT_DB_PATH,
        DEFAULT_SNAPSHOT_PATH,
        DEFAULT_STATUS_PATH,
        MARKETS,
        write_breakouts_json,
        write_json,
        write_snapshot_json,
    )
except ImportError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from ath_atl.tracker import (
        ATHATLStore,
        ATHATLTracker,
        BinanceClient,
        DEFAULT_BREAKOUTS_PATH,
        DEFAULT_DB_PATH,
        DEFAULT_SNAPSHOT_PATH,
        DEFAULT_STATUS_PATH,
        MARKETS,
        write_breakouts_json,
        write_json,
        write_snapshot_json,
    )


PAGE_CSS = """
:root {
  --bg: #f4f7f8;
  --card: #ffffff;
  --ink: #23303b;
  --muted: #728091;
  --line: #dbe4ea;
  --soft: #edf3f6;
  --green: #049e4a;
  --green-bg: #e7f7ee;
  --red: #d9484d;
  --red-bg: #fde9ea;
  --blue: #1967a8;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: ui-rounded, "Avenir Next", "PingFang SC", "Hiragino Sans GB", sans-serif;
}

.page {
  width: min(1880px, calc(100vw - 48px));
  margin: 0 auto;
  padding: 28px 0 36px;
}

.topbar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 22px;
}

h1 {
  margin: 0;
  font-size: clamp(36px, 4.6vw, 72px);
  line-height: 0.95;
  letter-spacing: -0.06em;
}

.subtitle {
  margin: 12px 0 0;
  color: var(--muted);
  font-size: 17px;
}

.nav {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.nav a,
button,
input,
select {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--card);
  color: var(--ink);
  font: inherit;
}

.nav a {
  padding: 12px 16px;
  text-decoration: none;
  color: var(--ink);
}

.nav a.active {
  background: var(--ink);
  color: #fff;
  border-color: var(--ink);
}

.stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.stat {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 18px;
}

.stat label {
  display: block;
  color: var(--muted);
  margin-bottom: 8px;
}

.stat strong {
  display: block;
  font-size: clamp(26px, 2.7vw, 46px);
  letter-spacing: -0.05em;
}

.panel {
  overflow: hidden;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 12px;
}

.panel + .panel { margin-top: 16px; }

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 14px;
  border-bottom: 1px solid var(--line);
}

.panel-title {
  font-weight: 800;
}

.tools {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

input,
select {
  height: 42px;
  padding: 0 12px;
  min-width: 170px;
}

button {
  height: 42px;
  padding: 0 16px;
  background: var(--ink);
  color: #fff;
  border-color: var(--ink);
  cursor: pointer;
}

.table-wrap {
  max-height: calc(100vh - 300px);
  overflow: auto;
}

table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  table-layout: fixed;
}

th,
td {
  padding: 15px 16px;
  border-bottom: 1px solid var(--line);
  text-align: left;
  white-space: nowrap;
}

th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--soft);
  color: #34424f;
  font-size: 14px;
  cursor: pointer;
}

td {
  font-size: 16px;
}

.num { text-align: right; font-variant-numeric: tabular-nums; }
.symbol { font-weight: 900; letter-spacing: -0.03em; }
.market { color: var(--muted); text-transform: uppercase; font-size: 13px; }
.high { color: var(--green); background: var(--green-bg); font-weight: 800; }
.low { color: var(--red); background: var(--red-bg); font-weight: 800; }
.muted { color: var(--muted); }
.scan-status { margin-top: 8px; color: var(--muted); font-size: 15px; }
.empty { padding: 40px 16px; color: var(--muted); text-align: center; }
.error { color: var(--red); }

@media (max-width: 900px) {
  .page { width: min(100vw - 20px, 900px); padding-top: 18px; }
  .topbar { align-items: flex-start; flex-direction: column; }
  .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .panel-head { align-items: stretch; flex-direction: column; }
  .tools { justify-content: stretch; }
  input, select, button { width: 100%; }
  th, td { padding: 12px 10px; }
}
"""


ATH_ATL_HTML = """
<!doctype html>
<html lang="zh-Hans">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ATH / ATL</title>
  <style>{css}</style>
</head>
<body>
  <main class="page">
    <header class="topbar">
      <div>
        <h1>ATH / ATL</h1>
        <p class="subtitle">独立读取 ath_atl/data 里的 SQLite，展示 Binance 现货和合约所有 USDT 交易对历史高低点。</p>
        <p class="scan-status" id="scan-status">后台扫描状态：Loading...</p>
      </div>
    </header>

    <section class="stats">
      <div class="stat"><label>币种数量</label><strong id="stat-count">-</strong></div>
      <div class="stat"><label>更新时间</label><strong id="stat-updated">-</strong></div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <div>
          <div class="panel-title">Daily Breakouts</div>
          <div class="muted">数据来自 ath_atl/data/daily_breakouts.json。</div>
        </div>
        <div class="tools">
          <input id="breakout-search" placeholder="Search symbol">
          <select id="breakout-type">
            <option value="">全部突破</option>
            <option value="new_high">New high</option>
            <option value="new_low">New low</option>
          </select>
          <button id="breakout-refresh">Refresh Breakouts</button>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th data-home-breakout-key="date">日期</th>
              <th data-home-breakout-key="symbol">币种</th>
              <th data-home-breakout-key="breakout_type">类型</th>
              <th class="num" data-home-breakout-key="price">突破价</th>
              <th class="num" data-home-breakout-key="previous_price">原高/低点</th>
            </tr>
          </thead>
          <tbody id="breakout-rows">
            <tr><td class="empty" colspan="5">Loading...</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <div>
          <div class="panel-title">All Symbols ATH / ATL</div>
          <div class="muted">同名币种只显示 K 线起点更早的一条；点击表头排序。</div>
        </div>
        <div class="tools">
          <input id="search" placeholder="Search symbol">
          <select id="limit">
            <option value="100">Top 100</option>
            <option value="300">Top 300</option>
            <option value="0">All</option>
          </select>
          <button id="refresh">Refresh</button>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th data-key="symbol">币种</th>
              <th class="num" data-key="current_price">当前价格</th>
              <th class="num" data-key="ath_price">ATH</th>
              <th class="num" data-key="atl_price">ATL</th>
              <th data-key="updated_at">更新</th>
            </tr>
          </thead>
          <tbody id="rows">
            <tr><td class="empty" colspan="5">Loading...</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </main>
  <script>{script}</script>
</body>
</html>
"""


BREAKOUTS_HTML = """
<!doctype html>
<html lang="zh-Hans">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ATH / ATL Breakouts</title>
  <style>{css}</style>
</head>
<body>
  <main class="page">
    <header class="topbar">
      <div>
        <h1>突破列表</h1>
        <p class="subtitle">单独展示最新扫描里突破历史新高或跌破历史新低的币。</p>
        <p class="scan-status" id="scan-status">后台扫描状态：Loading...</p>
      </div>
    </header>

    <section class="stats">
      <div class="stat"><label>突破数量</label><strong id="stat-count">-</strong></div>
      <div class="stat"><label>新高</label><strong id="stat-high">-</strong></div>
      <div class="stat"><label>新低</label><strong id="stat-low">-</strong></div>
      <div class="stat"><label>生成时间</label><strong id="stat-updated">-</strong></div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <div>
          <div class="panel-title">Daily Breakouts</div>
          <div class="muted">数据来自 ath_atl/data/daily_breakouts.json。</div>
        </div>
        <div class="tools">
          <input id="search" placeholder="Search symbol">
          <select id="type">
            <option value="">全部突破</option>
            <option value="new_high">New high</option>
            <option value="new_low">New low</option>
          </select>
          <button id="refresh">Refresh</button>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th data-breakout-key="date">日期</th>
              <th data-breakout-key="symbol">币种</th>
              <th data-breakout-key="breakout_type">类型</th>
              <th class="num" data-breakout-key="price">突破价</th>
              <th class="num" data-breakout-key="previous_price">原高/低点</th>
            </tr>
          </thead>
          <tbody id="rows">
            <tr><td class="empty" colspan="5">Loading...</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <div>
          <div class="panel-title">All Symbols ATH / ATL</div>
          <div class="muted">同名币种只显示 K 线起点更早的一条。</div>
        </div>
        <div class="tools">
          <input id="ath-search" placeholder="Search symbol">
          <select id="ath-limit">
            <option value="100">Top 100</option>
            <option value="300">Top 300</option>
            <option value="0">All</option>
          </select>
          <button id="ath-refresh">Refresh ATH/ATL</button>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th data-record-key="symbol">币种</th>
              <th class="num" data-record-key="current_price">当前价格</th>
              <th class="num" data-record-key="ath_price">ATH</th>
              <th class="num" data-record-key="atl_price">ATL</th>
              <th data-record-key="updated_at">更新</th>
            </tr>
          </thead>
          <tbody id="ath-rows">
            <tr><td class="empty" colspan="5">Loading...</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </main>
  <script>{script}</script>
</body>
</html>
"""


ATH_ATL_SCRIPT = """
let records = [];
let breakouts = [];
let scanStatus = {};
let sortKey = "symbol";
let sortDir = "asc";
let breakoutSortKey = "date";
let breakoutSortDir = "desc";

const fmtPrice = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  const number = Number(value);
  if (number === 0) return "$0";
  if (Math.abs(number) >= 1) return "$" + number.toLocaleString(undefined, { maximumFractionDigits: 8 });
  return "$" + number.toPrecision(6).replace(/0+$/, "").replace(/\\.$/, "");
};

function cleanDate(value) {
  if (!value) return "-";
  const text = String(value);
  if (/^\\d{4}-\\d{2}-\\d{2}$/.test(text)) return text;

  const normalized = text.includes("T") ? text : text.replace(" ", "T");
  const hasTimezone = /(?:Z|[+-]\\d{2}:?\\d{2})$/.test(normalized);
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

async function loadStatus() {
  try {
    const resp = await fetch("/api/status");
    scanStatus = await resp.json();
    const node = document.getElementById("scan-status");
    node.textContent = "后台扫描状态：" + describeStatus(scanStatus);
  } catch (error) {
    document.getElementById("scan-status").textContent = "后台扫描状态：读取失败";
  }
}

function describeStatus(status) {
  if (status.running) {
    return `扫描中，从 ${cleanDate(status.started_at)} 开始`;
  }
  if (status.error) {
    return `错误：${status.error}`;
  }
  if (status.finished_at) {
    return `上次完成 ${cleanDate(status.finished_at)}，下次 ${cleanDate(status.next_scan_at)}`;
  }
  return status.auto_scan ? "等待第一次扫描" : "自动扫描已关闭";
}

async function loadData() {
  const rows = document.getElementById("rows");
  rows.innerHTML = '<tr><td class="empty" colspan="5">Loading...</td></tr>';
  try {
    const resp = await fetch("/api/ath-atl");
    const data = await resp.json();
    records = data.records || [];
    render();
  } catch (error) {
    rows.innerHTML = '<tr><td class="empty error" colspan="5">Failed to load ATH/ATL data</td></tr>';
  }
}

async function loadBreakouts() {
  const rows = document.getElementById("breakout-rows");
  rows.innerHTML = '<tr><td class="empty" colspan="5">Loading...</td></tr>';
  try {
    const resp = await fetch("/api/breakouts");
    const data = await resp.json();
    breakouts = data.breakouts || [];
    renderBreakouts();
  } catch (error) {
    rows.innerHTML = '<tr><td class="empty error" colspan="5">Failed to load breakout data</td></tr>';
  }
}

function render() {
  const search = document.getElementById("search").value.trim().toUpperCase();
  const limit = Number(document.getElementById("limit").value);

  let filtered = records.filter((row) => {
    return !search || row.symbol.includes(search);
  });

  filtered.sort((a, b) => compareValues(a[sortKey], b[sortKey]) * (sortDir === "asc" ? 1 : -1));
  const shown = limit > 0 ? filtered.slice(0, limit) : filtered;

  document.getElementById("stat-count").textContent = filtered.length.toLocaleString();
  document.getElementById("stat-updated").textContent = cleanDate(records[0]?.updated_at);

  const rows = document.getElementById("rows");
  if (!shown.length) {
    const message = scanStatus.running
      ? "后台正在扫描，数据会自动出现。第一次全量历史 K 线会慢一点。"
      : "没有数据。后台会自动扫描，也可以手动运行 python3 -m ath_atl.tracker";
    rows.innerHTML = `<tr><td class="empty" colspan="5">${message}</td></tr>`;
    return;
  }

  rows.innerHTML = shown.map((row) => `
    <tr>
      <td class="symbol">${row.symbol}</td>
      <td class="num">${fmtPrice(row.current_price)}</td>
      <td class="num high">${fmtPrice(row.ath_price)}</td>
      <td class="num low">${fmtPrice(row.atl_price)}</td>
      <td class="muted">${cleanDate(row.updated_at)}</td>
    </tr>
  `).join("");
}

function renderBreakouts() {
  const search = document.getElementById("breakout-search").value.trim().toUpperCase();
  const type = document.getElementById("breakout-type").value;
  let filtered = breakouts.filter((row) => {
    const textMatch = !search || row.symbol.includes(search);
    const typeMatch = !type || row.breakout_type === type;
    return textMatch && typeMatch;
  });

  filtered.sort((a, b) => compareValues(a[breakoutSortKey], b[breakoutSortKey]) * (breakoutSortDir === "asc" ? 1 : -1));

  const rows = document.getElementById("breakout-rows");
  if (!filtered.length) {
    const message = scanStatus.running
      ? "后台正在扫描；如果有新高/新低，会自动出现在这里。"
      : "没有突破数据。后台会自动扫描，也可以手动运行 python3 -m ath_atl.tracker";
    rows.innerHTML = `<tr><td class="empty" colspan="5">${message}</td></tr>`;
    return;
  }

  rows.innerHTML = filtered.map((row) => {
    const typeLabel = row.breakout_type === "new_high" ? "New high" : "New low";
    const typeClass = row.breakout_type === "new_high" ? "high" : "low";
    return `
      <tr>
        <td>${row.date || "-"}</td>
        <td class="symbol">${row.symbol}</td>
        <td class="${typeClass}">${typeLabel}</td>
        <td class="num">${fmtPrice(row.price)}</td>
        <td class="num muted">${fmtPrice(row.previous_price)}</td>
      </tr>
    `;
  }).join("");
}

function compareValues(left, right) {
  const leftNum = Number(left);
  const rightNum = Number(right);
  if (!Number.isNaN(leftNum) && !Number.isNaN(rightNum)) return leftNum - rightNum;
  return String(left ?? "").localeCompare(String(right ?? ""));
}

document.querySelectorAll("th[data-key]").forEach((th) => {
  th.addEventListener("click", () => {
    const key = th.dataset.key;
    if (sortKey === key) {
      sortDir = sortDir === "asc" ? "desc" : "asc";
    } else {
      sortKey = key;
      sortDir = "asc";
    }
    render();
  });
});

document.querySelectorAll("th[data-home-breakout-key]").forEach((th) => {
  th.addEventListener("click", () => {
    const key = th.dataset.homeBreakoutKey;
    if (breakoutSortKey === key) {
      breakoutSortDir = breakoutSortDir === "asc" ? "desc" : "asc";
    } else {
      breakoutSortKey = key;
      breakoutSortDir = "asc";
    }
    renderBreakouts();
  });
});

document.getElementById("search").addEventListener("input", render);
document.getElementById("limit").addEventListener("change", render);
document.getElementById("refresh").addEventListener("click", loadData);
document.getElementById("breakout-search").addEventListener("input", renderBreakouts);
document.getElementById("breakout-type").addEventListener("change", renderBreakouts);
document.getElementById("breakout-refresh").addEventListener("click", loadBreakouts);
loadStatus();
loadBreakouts();
loadData();
setInterval(loadStatus, 5000);
setInterval(loadBreakouts, 30000);
setInterval(loadData, 30000);
"""


BREAKOUTS_SCRIPT = """
let breakouts = [];
let records = [];
let scanStatus = {};
let sortKey = "date";
let sortDir = "desc";
let recordSortKey = "symbol";
let recordSortDir = "asc";

const fmtPrice = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  const number = Number(value);
  if (number === 0) return "$0";
  if (Math.abs(number) >= 1) return "$" + number.toLocaleString(undefined, { maximumFractionDigits: 8 });
  return "$" + number.toPrecision(6).replace(/0+$/, "").replace(/\\.$/, "");
};

function cleanDate(value) {
  if (!value) return "-";
  const text = String(value);
  if (/^\\d{4}-\\d{2}-\\d{2}$/.test(text)) return text;

  const normalized = text.includes("T") ? text : text.replace(" ", "T");
  const hasTimezone = /(?:Z|[+-]\\d{2}:?\\d{2})$/.test(normalized);
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

async function loadStatus() {
  try {
    const resp = await fetch("/api/status");
    scanStatus = await resp.json();
    const node = document.getElementById("scan-status");
    node.textContent = "后台扫描状态：" + describeStatus(scanStatus);
  } catch (error) {
    document.getElementById("scan-status").textContent = "后台扫描状态：读取失败";
  }
}

function describeStatus(status) {
  if (status.running) {
    return `扫描中，从 ${cleanDate(status.started_at)} 开始`;
  }
  if (status.error) {
    return `错误：${status.error}`;
  }
  if (status.finished_at) {
    return `上次完成 ${cleanDate(status.finished_at)}，下次 ${cleanDate(status.next_scan_at)}`;
  }
  return status.auto_scan ? "等待第一次扫描" : "自动扫描已关闭";
}

async function loadData() {
  const rows = document.getElementById("rows");
  rows.innerHTML = '<tr><td class="empty" colspan="5">Loading...</td></tr>';
  try {
    const resp = await fetch("/api/breakouts");
    const data = await resp.json();
    breakouts = data.breakouts || [];
    document.getElementById("stat-updated").textContent = cleanDate(data.generated_at);
    render();
  } catch (error) {
    rows.innerHTML = '<tr><td class="empty error" colspan="5">Failed to load breakout data</td></tr>';
  }
}

async function loadAthData() {
  const rows = document.getElementById("ath-rows");
  rows.innerHTML = '<tr><td class="empty" colspan="5">Loading...</td></tr>';
  try {
    const resp = await fetch("/api/ath-atl");
    const data = await resp.json();
    records = data.records || [];
    renderAthTable();
  } catch (error) {
    rows.innerHTML = '<tr><td class="empty error" colspan="5">Failed to load ATH/ATL data</td></tr>';
  }
}

function render() {
  const search = document.getElementById("search").value.trim().toUpperCase();
  const type = document.getElementById("type").value;
  let filtered = breakouts.filter((row) => {
    const textMatch = !search || row.symbol.includes(search);
    const typeMatch = !type || row.breakout_type === type;
    return textMatch && typeMatch;
  });

  filtered.sort((a, b) => compareValues(a[sortKey], b[sortKey]) * (sortDir === "asc" ? 1 : -1));

  document.getElementById("stat-count").textContent = filtered.length.toLocaleString();
  document.getElementById("stat-high").textContent = filtered.filter((row) => row.breakout_type === "new_high").length.toLocaleString();
  document.getElementById("stat-low").textContent = filtered.filter((row) => row.breakout_type === "new_low").length.toLocaleString();

  const rows = document.getElementById("rows");
  if (!filtered.length) {
    const message = scanStatus.running
      ? "后台正在扫描；如果有新高/新低，会自动出现在这里。"
      : "没有突破数据。后台会自动扫描，也可以手动运行 python3 -m ath_atl.tracker";
    rows.innerHTML = `<tr><td class="empty" colspan="5">${message}</td></tr>`;
    return;
  }

  rows.innerHTML = filtered.map((row) => {
    const typeLabel = row.breakout_type === "new_high" ? "New high" : "New low";
    const typeClass = row.breakout_type === "new_high" ? "high" : "low";
    return `
      <tr>
        <td>${row.date || "-"}</td>
        <td class="symbol">${row.symbol}</td>
        <td class="${typeClass}">${typeLabel}</td>
        <td class="num">${fmtPrice(row.price)}</td>
        <td class="num muted">${fmtPrice(row.previous_price)}</td>
      </tr>
    `;
  }).join("");
}

function renderAthTable() {
  const search = document.getElementById("ath-search").value.trim().toUpperCase();
  const limit = Number(document.getElementById("ath-limit").value);

  let filtered = records.filter((row) => {
    return !search || row.symbol.includes(search);
  });

  filtered.sort((a, b) => compareValues(a[recordSortKey], b[recordSortKey]) * (recordSortDir === "asc" ? 1 : -1));
  const shown = limit > 0 ? filtered.slice(0, limit) : filtered;

  const rows = document.getElementById("ath-rows");
  if (!shown.length) {
    const message = scanStatus.running
      ? "后台正在扫描，ATH/ATL 数据会自动出现在这里。"
      : "没有 ATH/ATL 数据。后台会自动扫描，也可以手动运行 python3 -m ath_atl.tracker";
    rows.innerHTML = `<tr><td class="empty" colspan="5">${message}</td></tr>`;
    return;
  }

  rows.innerHTML = shown.map((row) => `
    <tr>
      <td class="symbol">${row.symbol}</td>
      <td class="num">${fmtPrice(row.current_price)}</td>
      <td class="num high">${fmtPrice(row.ath_price)}</td>
      <td class="num low">${fmtPrice(row.atl_price)}</td>
      <td class="muted">${cleanDate(row.updated_at)}</td>
    </tr>
  `).join("");
}

function compareValues(left, right) {
  const leftNum = Number(left);
  const rightNum = Number(right);
  if (!Number.isNaN(leftNum) && !Number.isNaN(rightNum)) return leftNum - rightNum;
  return String(left ?? "").localeCompare(String(right ?? ""));
}

document.querySelectorAll("th[data-breakout-key]").forEach((th) => {
  th.addEventListener("click", () => {
    const key = th.dataset.breakoutKey;
    if (sortKey === key) {
      sortDir = sortDir === "asc" ? "desc" : "asc";
    } else {
      sortKey = key;
      sortDir = "asc";
    }
    render();
  });
});

document.querySelectorAll("th[data-record-key]").forEach((th) => {
  th.addEventListener("click", () => {
    const key = th.dataset.recordKey;
    if (recordSortKey === key) {
      recordSortDir = recordSortDir === "asc" ? "desc" : "asc";
    } else {
      recordSortKey = key;
      recordSortDir = "asc";
    }
    renderAthTable();
  });
});

document.getElementById("search").addEventListener("input", render);
document.getElementById("type").addEventListener("change", render);
document.getElementById("refresh").addEventListener("click", loadData);
document.getElementById("ath-search").addEventListener("input", renderAthTable);
document.getElementById("ath-limit").addEventListener("change", renderAthTable);
document.getElementById("ath-refresh").addEventListener("click", loadAthData);
loadStatus();
loadData();
loadAthData();
setInterval(loadStatus, 5000);
setInterval(loadData, 30000);
setInterval(loadAthData, 30000);
"""


class BackgroundScanner:
    def __init__(
        self,
        db_path=DEFAULT_DB_PATH,
        breakouts_path=DEFAULT_BREAKOUTS_PATH,
        snapshot_path=DEFAULT_SNAPSHOT_PATH,
        status_path=DEFAULT_STATUS_PATH,
        market_types=None,
        symbols=None,
        max_symbols=None,
        request_delay=0.05,
        kline_limit=1000,
        interval_hours=24.0,
    ):
        self.db_path = Path(db_path)
        self.breakouts_path = Path(breakouts_path)
        self.snapshot_path = Path(snapshot_path)
        self.status_path = Path(status_path)
        self.market_types = market_types or ["spot", "futures"]
        self.symbols = symbols
        self.max_symbols = max_symbols
        self.request_delay = request_delay
        self.kline_limit = kline_limit
        self.interval_seconds = max(60, int(interval_hours * 60 * 60))
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.status = self.default_status(auto_scan=True)

    def default_status(self, auto_scan):
        return {
            "auto_scan": auto_scan,
            "running": False,
            "started_at": None,
            "finished_at": None,
            "next_scan_at": None,
            "error": None,
            "summary": {},
            "breakouts": 0,
        }

    def start(self):
        thread = threading.Thread(target=self.run_forever, name="ath-atl-scanner", daemon=True)
        thread.start()
        return thread

    def stop(self):
        self.stop_event.set()

    def get_status(self):
        with self.lock:
            return dict(self.status)

    def set_status(self, **updates):
        with self.lock:
            self.status.update(updates)
            payload = dict(self.status)
        write_json(self.status_path, payload)

    def run_forever(self):
        self.scan_once()
        while not self.stop_event.wait(self.interval_seconds):
            self.scan_once()

    def scan_once(self):
        started_at = now_iso()
        self.set_status(
            auto_scan=True,
            running=True,
            started_at=started_at,
            error=None,
            next_scan_at=None,
        )
        print(f"ATH/ATL scan started at {started_at}")

        store = None
        try:
            store = ATHATLStore(self.db_path)
            client = BinanceClient(request_delay=self.request_delay)
            tracker = ATHATLTracker(client=client, store=store, kline_limit=self.kline_limit)
            breakouts, summary = tracker.scan(
                market_types=self.market_types,
                symbols=self.symbols,
                max_symbols=self.max_symbols,
            )
            write_breakouts_json(self.breakouts_path, breakouts, summary)
            write_snapshot_json(self.snapshot_path, store.list_records())

            finished_at = now_iso()
            next_scan_at = future_iso(self.interval_seconds)
            self.set_status(
                running=False,
                finished_at=finished_at,
                next_scan_at=next_scan_at,
                error=None,
                summary=summary,
                breakouts=len(breakouts),
            )
            print(f"ATH/ATL scan finished at {finished_at}; breakouts: {len(breakouts)}")
        except Exception as exc:
            finished_at = now_iso()
            next_scan_at = future_iso(self.interval_seconds)
            self.set_status(
                running=False,
                finished_at=finished_at,
                next_scan_at=next_scan_at,
                error=str(exc),
            )
            print(f"ATH/ATL scan failed at {finished_at}: {exc}")
        finally:
            if store is not None:
                store.close()


class ATHATLHandler(BaseHTTPRequestHandler):
    db_path = DEFAULT_DB_PATH
    breakouts_path = DEFAULT_BREAKOUTS_PATH
    status_path = DEFAULT_STATUS_PATH
    scanner = None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path in {"/", "/ath-atl"}:
            self.send_html(ATH_ATL_HTML.format(css=PAGE_CSS, script=ATH_ATL_SCRIPT))
        elif path == "/breakouts":
            self.send_html(BREAKOUTS_HTML.format(css=PAGE_CSS, script=BREAKOUTS_SCRIPT))
        elif path == "/api/ath-atl":
            params = parse_qs(parsed.query)
            self.send_json({"records": load_records(self.db_path, params)})
        elif path == "/api/breakouts":
            self.send_json(load_breakouts(self.breakouts_path, self.db_path))
        elif path == "/api/status":
            self.send_json(load_status(self.status_path, self.scanner))
        else:
            self.send_error(404, "Not found")

    def log_message(self, fmt, *args):
        return

    def send_html(self, html):
        payload = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_json(self, data):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def load_records(db_path, params=None):
    db_path = Path(db_path)
    if not db_path.exists():
        return []

    store = ATHATLStore(db_path)
    try:
        records = store.list_records()
    finally:
        store.close()

    params = params or {}
    market = first_param(params, "market_type")
    symbol = first_param(params, "symbol")

    if market:
        records = [row for row in records if row["market_type"] == market]
    if symbol:
        symbol = symbol.upper()
        records = [row for row in records if symbol in row["symbol"]]

    return dedupe_records_by_symbol(records)


def dedupe_records_by_symbol(records):
    selected = {}
    for row in records:
        symbol = row["symbol"]
        current = selected.get(symbol)
        if current is None or record_sort_key(row) < record_sort_key(current):
            selected[symbol] = normalized_record(row)
    return sorted(selected.values(), key=lambda item: item["symbol"])


def normalized_record(row):
    item = dict(row)
    if not item.get("first_kline_date"):
        item["first_kline_date"] = first_available_date(item)
    return item


def record_sort_key(row):
    first_open_time = int(row.get("first_kline_open_time") or 0)
    if first_open_time > 0:
        start_key = first_open_time
    else:
        start_key = date_to_sort_key(first_available_date(row))

    # If the historical start is identical, prefer spot for a stable display.
    market_priority = 0 if row.get("market_type") == "spot" else 1
    return (start_key, market_priority)


def first_available_date(row):
    dates = [
        row.get("first_kline_date"),
        row.get("ath_date"),
        row.get("atl_date"),
    ]
    valid_dates = [date for date in dates if date]
    return min(valid_dates) if valid_dates else None


def date_to_sort_key(value):
    if not value:
        return 9999999999999
    try:
        dt = datetime.fromisoformat(str(value)[:10]).replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return 9999999999999


def load_breakouts(path, db_path=None):
    path = Path(path)
    if not path.exists():
        return {"generated_at": None, "date": None, "summary": {}, "breakouts": []}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"generated_at": None, "date": None, "summary": {}, "breakouts": []}

    payload["breakouts"] = dedupe_breakouts(payload.get("breakouts", []), db_path)
    return payload


def dedupe_breakouts(breakouts, db_path=None):
    preferred_market = {}
    if db_path:
        preferred_market = {row["symbol"]: row.get("market_type") for row in load_records(db_path)}

    selected = {}
    for row in breakouts:
        key = (row.get("date"), row.get("symbol"), row.get("breakout_type"))
        current = selected.get(key)
        if current is None:
            selected[key] = row
            continue

        symbol = row.get("symbol")
        market = preferred_market.get(symbol)
        if market and row.get("market_type") == market and current.get("market_type") != market:
            selected[key] = row

    return sorted(
        selected.values(),
        key=lambda item: (item.get("date") or "", item.get("symbol") or "", item.get("breakout_type") or ""),
        reverse=True,
    )


def load_status(path, scanner=None):
    if scanner is not None:
        return scanner.get_status()

    path = Path(path)
    if not path.exists():
        return {
            "auto_scan": False,
            "running": False,
            "started_at": None,
            "finished_at": None,
            "next_scan_at": None,
            "error": None,
            "summary": {},
            "breakouts": 0,
        }

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "auto_scan": False,
            "running": False,
            "started_at": None,
            "finished_at": None,
            "next_scan_at": None,
            "error": "scan_status.json is not valid JSON",
            "summary": {},
            "breakouts": 0,
        }


def first_param(params, key):
    values = params.get(key) or []
    return values[0] if values else None


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def future_iso(seconds):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(timespec="seconds")


def parse_args():
    parser = argparse.ArgumentParser(description="Serve ATH/ATL records and daily breakouts")
    parser.add_argument("--host", default="127.0.0.1", help="bind host")
    parser.add_argument("--port", type=int, default=8788, help="bind port")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--breakouts-path", default=str(DEFAULT_BREAKOUTS_PATH), help="daily breakouts JSON path")
    parser.add_argument("--snapshot-path", default=str(DEFAULT_SNAPSHOT_PATH), help="ATH/ATL snapshot JSON path")
    parser.add_argument("--status-path", default=str(DEFAULT_STATUS_PATH), help="scan status JSON path")
    parser.add_argument(
        "--market-types",
        nargs="+",
        choices=sorted(MARKETS),
        default=["spot", "futures"],
        help="markets to scan in the background, default: spot futures",
    )
    parser.add_argument("--symbols", help="comma-separated symbols for targeted background scans")
    parser.add_argument("--max-symbols", type=int, help="limit symbols per market for testing")
    parser.add_argument("--request-delay", type=float, default=0.05, help="seconds between paginated kline requests")
    parser.add_argument("--kline-limit", type=int, default=1000, help="Binance kline page size")
    parser.add_argument("--scan-interval-hours", type=float, default=4.0, help="background scan interval")
    parser.add_argument("--no-auto-scan", action="store_true", help="serve pages without starting background scans")
    return parser.parse_args()


def main():
    args = parse_args()
    handler = ATHATLHandler
    handler.db_path = Path(args.db_path)
    handler.breakouts_path = Path(args.breakouts_path)
    handler.status_path = Path(args.status_path)

    scanner = None
    if not args.no_auto_scan:
        symbols = args.symbols.split(",") if args.symbols else None
        scanner = BackgroundScanner(
            db_path=args.db_path,
            breakouts_path=args.breakouts_path,
            snapshot_path=args.snapshot_path,
            status_path=args.status_path,
            market_types=args.market_types,
            symbols=symbols,
            max_symbols=args.max_symbols,
            request_delay=args.request_delay,
            kline_limit=args.kline_limit,
            interval_hours=args.scan_interval_hours,
        )
        handler.scanner = scanner
    else:
        handler.scanner = None
        write_json(args.status_path, BackgroundScanner().default_status(auto_scan=False))

    server = ThreadingHTTPServer((args.host, args.port), handler)
    if scanner:
        scanner.start()
    print(f"ATH/ATL page: http://{args.host}:{args.port}/")
    print(f"Breakouts page: http://{args.host}:{args.port}/breakouts")
    if scanner:
        print("Background ATH/ATL scan: enabled")
    else:
        print("Background ATH/ATL scan: disabled")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ATH/ATL web server")
    finally:
        if scanner:
            scanner.stop()
        server.server_close()


if __name__ == "__main__":
    main()
