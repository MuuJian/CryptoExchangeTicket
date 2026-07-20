import { applyLivePriceToRow } from "../utils/rankingRows.js";

const OPTIONAL_NUMBER_FIELDS = [
  "changePercent",
  "priceChangePercent",
  "fundingRatePercent",
  "oi24hChangePercent",
  "oi7dChangePercent",
];

export function useOiRankingData() {
  const rowsBySymbol = new Map();
  let rows = [];
  let version = 0;
  let stats = buildStats(rows);

  function setRows(nextRows, priceMap) {
    const seen = new Set();

    for (const item of nextRows) {
      if (!isOiRow(item)) continue;

      const row = { ...item };
      applyLivePriceToRow(row, priceMap.get(item.symbol));
      rowsBySymbol.set(item.symbol, row);
      seen.add(item.symbol);
    }

    for (const symbol of rowsBySymbol.keys()) {
      if (!seen.has(symbol)) rowsBySymbol.delete(symbol);
    }

    rows = [...rowsBySymbol.values()];
    stats = buildStats(rows);
    version += 1;
  }

  function applyPriceUpdates(symbols, priceMap) {
    const affectedSymbols = [];

    for (const symbol of symbols) {
      const row = rowsBySymbol.get(symbol);
      if (!row) continue;
      if (applyLivePriceToRow(row, priceMap.get(symbol))) {
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

export async function loadOiSnapshot() {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 8000);
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
    if (error.name === "AbortError") throw new Error("OI 请求超时");
    throw error;
  } finally {
    window.clearTimeout(timeout);
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
  const rowsWith24hOi = rows.filter(row => row.oi24hChangePercent != null);
  const byIncrease = rowsWith24hOi
    .slice()
    .sort((a, b) => (b.oi24hChangePercent || 0) - (a.oi24hChangePercent || 0));
  const byDecrease = rowsWith24hOi
    .slice()
    .sort((a, b) => (a.oi24hChangePercent || 0) - (b.oi24hChangePercent || 0));

  return {
    changeCount: rows.filter(row => row.changePercent != null).length,
    topIncrease: byIncrease[0] || null,
    topDecrease: byDecrease[0] || null,
  };
}
