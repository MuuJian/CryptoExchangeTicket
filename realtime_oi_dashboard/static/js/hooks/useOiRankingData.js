import { applyLivePriceToRow } from "../utils/rankingRows.js";

export function useOiRankingData() {
  const rowsBySymbol = new Map();
  let rows = [];
  let version = 0;
  let oiVersion = 0;
  let priceVersion = 0;
  let stats = buildStats(rows);

  function setRows(nextRows, priceMap) {
    const seen = new Set();

    for (const item of nextRows) {
      if (!item || !item.symbol) continue;

      const row = rowsBySymbol.get(item.symbol) || {};
      Object.assign(row, item);
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
    oiVersion += 1;
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
      priceVersion += 1;
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
    getOiVersion() {
      return oiVersion;
    },
    getPriceVersion() {
      return priceVersion;
    },
  };
}

export async function loadOiSnapshot() {
  const res = await fetch("/api/oi");
  if (!res.ok) throw new Error("Cannot load OI data");
  return res.json();
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
