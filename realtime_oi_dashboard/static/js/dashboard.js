import { createFilterBar } from "./components/FilterBar.js";
import { createHighOi7dTable } from "./components/HighOi7dTable.js";
import { createOiRankingTable } from "./components/OiRankingTable.js";
import { createSortableHeaders } from "./components/SortableHeader.js";
import { renderStatCards, renderWsState } from "./components/StatCard.js";
import { useBinancePriceSocket } from "./hooks/useBinancePriceSocket.js";
import { useFavorites } from "./hooks/useFavorites.js";
import { loadOiSnapshot, useOiRankingData } from "./hooks/useOiRankingData.js";
import { useTableFilters } from "./hooks/useTableFilters.js";
import { useTableSort } from "./hooks/useTableSort.js";
import {
  buildHighOi7dRows,
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
  highOi7dBody: document.getElementById("highOi7dBody"),
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
let highOi7dFrame = 0;
let pendingPatchSymbols = new Set();
let visibleRowsCache = {
  deps: "",
  rows: [],
};

const table = createOiRankingTable({
  tbody: elements.rankBody,
  getRowBySymbol: rankingData.getRow,
});

const highOi7dTable = createHighOi7dTable({
  tbody: elements.highOi7dBody,
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
    scheduleHighOi7dRender();
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
const refreshTimer = window.setInterval(() => refreshOi({ showError: false }), 10000);
window.addEventListener("beforeunload", () => {
  window.clearInterval(refreshTimer);
  priceSocket.close();
});

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
  elements.statusTitle.textContent = payload.error
    ? "OI update error"
    : payload.rows?.length ? "Live OI changes" : "Waiting for fresh OI";
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
  renderHighOi7d();
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

function scheduleHighOi7dRender() {
  if (fullRenderFrame || highOi7dFrame) return;
  highOi7dFrame = window.requestAnimationFrame(() => {
    highOi7dFrame = 0;
    renderHighOi7d();
  });
}

function renderHighOi7d() {
  highOi7dTable.render(buildHighOi7dRows(rankingData.getRows()));
}

function cancelPendingPatch() {
  if (patchFrame) {
    window.cancelAnimationFrame(patchFrame);
    patchFrame = 0;
  }
  if (highOi7dFrame) {
    window.cancelAnimationFrame(highOi7dFrame);
    highOi7dFrame = 0;
  }
  pendingPatchSymbols.clear();
}
