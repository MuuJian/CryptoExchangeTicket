import { applyLivePriceToRow } from "../utils/rankingRows.js";

const OPTIONAL_NUMBER_FIELDS = [
  "changePercent",
  "priceChangePercent",
  "fundingRatePercent",
  "oi24hChangePercent",
  "oi7dChangePercent",
];
const LIVE_MARKET_FIELDS = [
  "price",
  "volume24h",
  "priceChangePercent",
  "currentOiValue",
];

export function useOiRankingData() {
  const serverRowsBySymbol = new Map();
  const rowsBySymbol = new Map();
  let rows = [];
  let version = 0;
  let stats = buildStats(rows);

  function setRows(nextRows, priceMap) {
    const seen = new Set();

    for (const item of nextRows) {
      if (!isOiRow(item)) continue;

      const serverRow = { ...item };
      const row = { ...serverRow };
      applyLivePriceToRow(row, priceMap.get(item.symbol));
      serverRowsBySymbol.set(item.symbol, serverRow);
      rowsBySymbol.set(item.symbol, row);
      seen.add(item.symbol);
    }

    for (const symbol of rowsBySymbol.keys()) {
      if (seen.has(symbol)) continue;
      serverRowsBySymbol.delete(symbol);
      rowsBySymbol.delete(symbol);
    }

    rows = [...rowsBySymbol.values()];
    stats = buildStats(rows);
    version += 1;
  }

  function applyPriceUpdates(symbols, priceMap) {
    const affectedSymbols = [];

    for (const symbol of symbols) {
      const row = rowsBySymbol.get(symbol);
      const serverRow = serverRowsBySymbol.get(symbol);
      if (!row || !serverRow) continue;

      const livePrice = priceMap.get(symbol);
      const changed = livePrice
        ? applyLivePriceToRow(row, livePrice)
        : restoreServerMarketData(row, serverRow);
      if (changed) {
        affectedSymbols.push(symbol);
      }
    }

    if (affectedSymbols.length) {
      version += 1;
    }

    return affectedSymbols;
  }

  return {
    setRows,
    applyPriceUpdates,
    getRows() {
      return rows;
    },
    getRow(symbol) {
      return rowsBySymbol.get(symbol);
    },
    getStats() {
      return stats;
    },
    getVersion() {
      return version;
    },
  };
}

function restoreServerMarketData(row, serverRow) {
  let changed = false;
  for (const field of LIVE_MARKET_FIELDS) {
    if (row[field] === serverRow[field]) continue;
    row[field] = serverRow[field];
    changed = true;
  }
  return changed;
}

export async function loadOiSnapshot({ signal } = {}) {
  const controller = new AbortController();
  let abortReason = null;
  const abort = reason => {
    abortReason ??= reason;
    controller.abort();
  };
  const timeout = window.setTimeout(() => abort("timeout"), 8000);
  const abortRequest = () => abort("cancelled");
  if (signal?.aborted) {
    abortRequest();
  } else {
    signal?.addEventListener("abort", abortRequest, { once: true });
  }
  try {
    const response = await fetch("/api/oi", {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`OI 请求失败 (${response.status})`);
    const payload = await response.json();
    if (
      !payload
      || !Array.isArray(payload.rows)
      || !payload.rows.every(isOiRow)
    ) {
      throw new Error("OI 响应格式错误");
    }
    return payload;
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error(
        abortReason === "cancelled" ? "OI 请求已取消" : "OI 请求超时",
      );
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
    signal?.removeEventListener("abort", abortRequest);
  }
}

function isOiRow(item) {
  if (
    !item
    || typeof item !== "object"
    || typeof item.symbol !== "string"
    || !item.symbol.trim()
    || item.symbol !== item.symbol.trim()
    || !isPositiveNumber(item.price)
    || !isNonNegativeNumber(item.currentOi)
    || !isNonNegativeNumber(item.currentOiValue)
    || !isOptionalNonNegativeNumber(item.volume24h)
    || !isOptionalTimestamp(item.nextFundingTime)
  ) return false;

  return OPTIONAL_NUMBER_FIELDS.every(field => isOptionalNumber(item[field]));
}

function isPositiveNumber(value) {
  return isFiniteNumber(value) && value > 0;
}

function isNonNegativeNumber(value) {
  return isFiniteNumber(value) && value >= 0;
}

function isOptionalNumber(value) {
  return value == null || isFiniteNumber(value);
}

function isOptionalNonNegativeNumber(value) {
  return value == null || isNonNegativeNumber(value);
}

function isOptionalTimestamp(value) {
  return value == null || (Number.isSafeInteger(value) && value > 0);
}

function isFiniteNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function buildStats(rows) {
  let changeCount = 0;
  let topIncrease = null;
  let topDecrease = null;

  for (const row of rows) {
    if (row.changePercent != null) changeCount += 1;

    const change = row.oi24hChangePercent;
    if (change > 0 && (!topIncrease || change > topIncrease.oi24hChangePercent)) {
      topIncrease = row;
    } else if (
      change < 0
      && (!topDecrease || change < topDecrease.oi24hChangePercent)
    ) {
      topDecrease = row;
    }
  }

  return {
    changeCount,
    topIncrease,
    topDecrease,
  };
}
