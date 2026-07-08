import {
  binanceFuturesUrl,
  formatWeightPercent,
} from "./format.js";

const EMPTY_MESSAGE = "没有指数组成记录。";
const SOURCE_LABELS = {
  binancefuture: "binancefuture",
  alpha: "alpha",
  aster: "aster",
  gate: "gate",
  bitget: "bitget",
  bybit: "bybit",
  kucoin: "kucoin",
  pancakev3: "pancakev3",
  pancakev2: "pancakev2",
};

export function createIndexConstituentsTable({ headerRow, tbody, getSortState, onSort }) {
  let sources = [];

  function render(rows, nextSources) {
    sources = nextSources;
    renderHeaders();
    tbody.textContent = "";

    if (!rows.length) {
      tbody.append(createEmptyRow(EMPTY_MESSAGE, sources.length + 2));
      return;
    }

    const fragment = document.createDocumentFragment();
    rows.forEach((row, index) => {
      fragment.append(createIndexConstituentRow(row, index + 1, sources));
    });
    tbody.append(fragment);
  }

  function renderMessage(message, nextSources = sources) {
    sources = nextSources;
    renderHeaders();
    tbody.textContent = "";
    tbody.append(createEmptyRow(message, sources.length + 2));
  }

  return {
    render,
    renderMessage,
  };

  function renderHeaders() {
    headerRow.textContent = "";
    headerRow.append(
      createStaticHeaderCell("排名"),
      createHeaderCell("symbol", "币种"),
    );

    for (const source of sources) {
      headerRow.append(createHeaderCell(`source:${source}`, sourceLabel(source)));
    }
  }

  function createStaticHeaderCell(label) {
    const th = document.createElement("th");
    th.textContent = label;
    return th;
  }

  function createHeaderCell(sortKey, label) {
    const th = document.createElement("th");
    th.dataset.sort = sortKey;
    th.append(createSortLabel(label));

    const sortState = getSortState();
    if (sortState.sortKey === sortKey) {
      th.classList.add(sortState.sortDir === "asc" ? "sorted-asc" : "sorted-desc");
    }

    th.addEventListener("click", () => onSort(sortKey));
    return th;
  }
}

function createIndexConstituentRow(row, rank, sources) {
  const tr = document.createElement("tr");

  const rankCell = document.createElement("td");
  rankCell.textContent = String(rank);

  const symbolCell = document.createElement("td");
  const symbolLink = document.createElement("a");
  symbolLink.className = "symbol-link symbol";
  symbolLink.href = binanceFuturesUrl(row.symbol);
  symbolLink.target = "_blank";
  symbolLink.rel = "noreferrer";
  symbolLink.textContent = row.symbol;
  symbolCell.append(symbolLink);

  tr.append(rankCell, symbolCell);

  for (const source of sources) {
    const weightCell = document.createElement("td");
    const weight = row.weights[source] ?? 0;
    weightCell.className = "weight-cell";
    weightCell.textContent = formatWeightPercent(weight);
    tr.append(weightCell);
  }
  return tr;
}

function createSortLabel(label) {
  const wrapper = document.createElement("span");
  wrapper.className = "sort-label";
  wrapper.textContent = label;

  const arrows = document.createElement("span");
  arrows.className = "sort-arrows";
  wrapper.append(arrows);
  return wrapper;
}

function createEmptyRow(message, colSpan) {
  const tr = document.createElement("tr");
  const td = document.createElement("td");
  td.colSpan = Math.max(2, colSpan);
  td.className = "empty";
  td.textContent = message;
  tr.append(td);
  return tr;
}

export function sourceLabel(source) {
  return SOURCE_LABELS[source] || source || "-";
}
