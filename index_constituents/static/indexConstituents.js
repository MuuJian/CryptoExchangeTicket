import { createIndexConstituentsTable, sourceLabel } from "./IndexConstituentsTable.js";
import {
  buildIndexWeightRows,
  filterIndexWeightRows,
  getIndexWeightSources,
  loadIndexConstituents,
  sortIndexWeightRows,
} from "./indexConstituentsData.js";
import { useTableSort } from "./useTableSort.js";

const elements = {
  statusText: document.getElementById("indexStatusText"),
  searchInput: document.getElementById("indexSearchInput"),
  sourceFilter: document.getElementById("indexSourceFilter"),
  refreshBtn: document.getElementById("indexRefreshBtn"),
  headerRow: document.getElementById("indexConstituentsHeader"),
  tbody: document.getElementById("indexConstituentsBody"),
};

const sort = useTableSort({
  sortKey: "source:binancefuture",
  sortDir: "desc",
});
const table = createIndexConstituentsTable({
  headerRow: elements.headerRow,
  tbody: elements.tbody,
  getSortState: sort.getState,
  onSort(sortKey) {
    sort.setSortKey(sortKey);
    renderRows();
  },
});

let weightRows = [];
let sources = getIndexWeightSources([]);
let pollTimer = 0;

elements.searchInput.addEventListener("input", renderRows);
elements.sourceFilter.addEventListener("change", renderRows);
elements.refreshBtn.addEventListener("click", () => startScan());

startScan();

async function startScan() {
  clearPollTimer();
  setLoading(true);
  table.renderMessage("正在启动扫描。", sources);

  try {
    const payload = await loadIndexConstituents({ refresh: true });
    handlePayload(payload);
    schedulePollIfNeeded(payload);
  } catch (error) {
    handleError(error);
  }
}

async function pollScan() {
  try {
    const payload = await loadIndexConstituents();
    handlePayload(payload);
    schedulePollIfNeeded(payload);
  } catch (error) {
    handleError(error);
  }
}

function handlePayload(payload) {
  weightRows = buildIndexWeightRows(payload.rows || []);
  sources = getIndexWeightSources(weightRows);
  populateSourceFilter(sources);
  renderStatus(payload);

  if (!weightRows.length && payload.scan_status === "running") {
    table.renderMessage("正在扫描 Binance 指数组成。", sources);
  } else {
    renderRows();
  }

  setLoading(payload.scan_status === "running");
}

function handleError(error) {
  weightRows = [];
  elements.statusText.textContent = error.message;
  table.renderMessage(error.message, sources);
  setLoading(false);
  clearPollTimer();
}

function schedulePollIfNeeded(payload) {
  clearPollTimer();
  if (payload.scan_status === "running") {
    pollTimer = window.setTimeout(pollScan, 700);
  }
}

function clearPollTimer() {
  if (!pollTimer) return;
  window.clearTimeout(pollTimer);
  pollTimer = 0;
}

function renderRows() {
  const filteredRows = filterIndexWeightRows(weightRows, {
    query: elements.searchInput.value,
    source: elements.sourceFilter.value,
  });
  table.render(sortIndexWeightRows(filteredRows, sort.getState()), sources);
}

function renderStatus(payload) {
  const errorText = payload.error_count ? ` · errors ${payload.error_count}` : "";
  const scannedText = `${payload.scanned_symbols || 0}/${payload.total_symbols || 0}`;
  const statusText = payload.scan_status === "running" ? "扫描中" : "扫描完成";
  elements.statusText.textContent =
    `${statusText} · ${scannedText} symbols · ${weightRows.length} rows · ${payload.duration_seconds || 0}s${errorText}`;
}

function populateSourceFilter(nextSources) {
  const currentValue = elements.sourceFilter.value;

  elements.sourceFilter.textContent = "";
  elements.sourceFilter.append(new Option("来源: 全部", ""));
  for (const source of nextSources) {
    elements.sourceFilter.append(new Option(sourceLabel(source), source));
  }

  if (nextSources.includes(currentValue)) {
    elements.sourceFilter.value = currentValue;
  }
}

function setLoading(isLoading) {
  elements.refreshBtn.disabled = isLoading;
  elements.refreshBtn.textContent = isLoading ? "扫描中" : "刷新";
}
