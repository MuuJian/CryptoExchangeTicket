import { createFilterBar } from "./components/FilterBar.js";
import { createOiRankingTable } from "./components/OiRankingTable.js";
import { createSortableHeaders } from "./components/SortableHeader.js";
import { renderStatCards, renderWsState } from "./components/StatCard.js";
import { useBinancePriceSocket } from "./hooks/useBinancePriceSocket.js";
import { useFavorites } from "./hooks/useFavorites.js";
import { loadOiSnapshot, useOiRankingData } from "./hooks/useOiRankingData.js";
import { useTableFilters } from "./hooks/useTableFilters.js";
import { useTableSort } from "./hooks/useTableSort.js";
import {
  buildVisibleRows,
  getHeatMax,
  isPriceDrivenView,
} from "./utils/rankingRows.js";

const elements = {
  statusTitle: document.getElementById("statusTitle"),
  statusText: document.getElementById("statusText"),
  changeCount: document.getElementById("changeCount"),
  wsState: document.getElementById("wsState"),
  topIncrease: document.getElementById("topIncrease"),
  topIncreaseNote: document.getElementById("topIncreaseNote"),
  topDecrease: document.getElementById("topDecrease"),
  topDecreaseNote: document.getElementById("topDecreaseNote"),
  searchInput: document.getElementById("searchInput"),
  favoritesOnlyBtn: document.getElementById("favoritesOnlyBtn"),
  oiValueFilter: document.getElementById("oiValueFilter"),
  volumeFilter: document.getElementById("volumeFilter"),
  limitSelect: document.getElementById("limitSelect"),
  rankBody: document.getElementById("rankBody"),
  sortableHeaders: document.querySelectorAll("th[data-sort]"),
};

const rankingData = useOiRankingData();
const favorites = useFavorites("oiFavorites");
const filters = useTableFilters({
  query: elements.searchInput.value.trim().toUpperCase(),
  limit: Number(elements.limitSelect.value),
  minOiValue: Number(elements.oiValueFilter.value),
  minVolume: Number(elements.volumeFilter.value),
});
const sort = useTableSort();

let heatMax = getHeatMax([]);
let fullRenderFrame = 0;
let patchFrame = 0;
let pendingPatchSymbols = new Set();
let visibleRowsCache = {
  deps: "",
  rows: [],
};

const table = createOiRankingTable({
  tbody: elements.rankBody,
  getRowBySymbol: rankingData.getRow,
});

const filterBar = createFilterBar({
  elements,
  filters,
  favorites,
  onChange: scheduleFullRender,
});

const sortableHeaders = createSortableHeaders({
  headers: elements.sortableHeaders,
  sort,
  onChange: scheduleFullRender,
});

const priceSocket = useBinancePriceSocket({
  onStatusChange(value) {
    renderWsState(elements.wsState, value);
  },
  onPricesChange(changedSymbols, priceMap) {
    const affectedSymbols = rankingData.applyPriceUpdates(changedSymbols, priceMap);
    if (!affectedSymbols.length) return;

    if (isPriceDrivenView(filters.getState(), sort.getState())) {
      scheduleFullRender();
      return;
    }

    scheduleRowPatch(affectedSymbols);
  },
});

elements.rankBody.addEventListener("click", event => {
  const target = event.target instanceof Element ? event.target : null;
  const button = target?.closest("[data-favorite]");
  if (!button) return;

  const symbol = button.dataset.favorite;
  favorites.toggle(symbol);
  filterBar.render();

  if (filters.getState().favoritesOnly) {
    scheduleFullRender();
  } else {
    scheduleRowPatch([symbol]);
  }
});

filterBar.render();
sortableHeaders.render();
priceSocket.connect();
refreshOi({ showError: true });
window.setInterval(() => refreshOi({ showError: false }), 10000);

async function refreshOi({ showError }) {
  try {
    const payload = await loadOiSnapshot();
    rankingData.setRows(payload.rows || [], priceSocket.getPrices());
    renderOiStatus(payload);
    renderStatCards(elements, rankingData.getStats());
    scheduleFullRender();
  } catch (error) {
    if (!showError) return;
    elements.statusTitle.textContent = "OI error";
    elements.statusText.textContent = error.message;
  }
}

function renderOiStatus(payload) {
  elements.statusTitle.textContent = payload.baseline ? "Baseline ready" : "Live OI changes";
  const errorText = payload.recent_errors?.length ? ` · errors ${payload.recent_errors.length}` : "";
  elements.statusText.textContent =
    `${payload.saved_at || "no OI yet"} · batch ${payload.updated_symbols || 0}/${payload.total_symbols || 0}${errorText}`;
}

function scheduleFullRender() {
  if (fullRenderFrame) return;
  fullRenderFrame = window.requestAnimationFrame(renderFull);
}

function scheduleRowPatch(symbols) {
  if (fullRenderFrame) return;

  for (const symbol of symbols) {
    pendingPatchSymbols.add(symbol);
  }

  if (patchFrame) return;
  patchFrame = window.requestAnimationFrame(() => {
    patchFrame = 0;
    const symbolsToPatch = new Set(pendingPatchSymbols);
    pendingPatchSymbols.clear();
    table.patchRows(symbolsToPatch, getRowRenderContext());
  });
}

function renderFull() {
  fullRenderFrame = 0;
  cancelPendingPatch();

  const visibleRows = getVisibleRows();
  heatMax = getHeatMax(visibleRows);
  table.render(visibleRows, getRowRenderContext());
  filterBar.render();
  sortableHeaders.render();
}

function getVisibleRows() {
  const deps = [
    rankingData.getVersion(),
    filters.getVersion(),
    sort.getVersion(),
    favorites.getVersion(),
  ].join(":");

  if (visibleRowsCache.deps !== deps) {
    visibleRowsCache = {
      deps,
      rows: buildVisibleRows(
        rankingData.getRows(),
        filters.getState(),
        sort.getState(),
        favorites.getSet(),
      ),
    };
  }

  return visibleRowsCache.rows;
}

function getRowRenderContext() {
  return {
    favorites: favorites.getSet(),
    heatMax,
  };
}

function cancelPendingPatch() {
  if (patchFrame) {
    window.cancelAnimationFrame(patchFrame);
    patchFrame = 0;
  }
  pendingPatchSymbols.clear();
}
