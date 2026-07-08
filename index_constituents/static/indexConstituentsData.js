export const PREFERRED_INDEX_SOURCES = [
  "binancefuture",
  "alpha",
  "aster",
  "gate",
  "bitget",
  "bybit",
  "kucoin",
  "pancakev3",
  "pancakev2",
];

export async function loadIndexConstituents({ refresh = false } = {}) {
  const url = refresh ? "/api/index-constituents?refresh=1" : "/api/index-constituents";
  const res = await fetch(url);
  if (!res.ok) throw new Error("Cannot load index constituents");
  return res.json();
}

export function buildIndexWeightRows(rows) {
  const rowsBySymbol = new Map();

  for (const item of rows) {
    if (!item?.symbol || !item.exchange) continue;
    const source = normalizeIndexSource(item.exchange);

    const row = rowsBySymbol.get(item.symbol) || {
      symbol: item.symbol,
      weights: {},
      sourceCount: 0,
      totalWeightPercent: 0,
      maxWeightPercent: 0,
    };
    const weight = typeof item.weightPercent === "number" && !Number.isNaN(item.weightPercent)
      ? item.weightPercent
      : null;

    if (weight != null) {
      row.weights[source] = (row.weights[source] || 0) + weight;
    } else if (!(source in row.weights)) {
      row.weights[source] = null;
    }

    rowsBySymbol.set(item.symbol, row);
  }

  const groupedRows = [...rowsBySymbol.values()];
  for (const row of groupedRows) {
    const weights = Object.values(row.weights).filter(value => value != null);
    row.sourceCount = Object.keys(row.weights).length;
    row.totalWeightPercent = weights.reduce((sum, value) => sum + value, 0);
    row.maxWeightPercent = weights.length ? Math.max(...weights) : 0;
  }

  return groupedRows;
}

export function getIndexWeightSources(rows) {
  return PREFERRED_INDEX_SOURCES;
}

export function filterIndexWeightRows(rows, { query, source }) {
  const normalizedQuery = query.trim().toLowerCase();
  return rows.filter(row => {
    if (source && row.weights[source] == null) return false;
    if (!normalizedQuery) return true;

    if (row.symbol.toLowerCase().includes(normalizedQuery)) return true;
    return Object.keys(row.weights).some(value => value.toLowerCase().includes(normalizedQuery));
  });
}

export function sortIndexWeightRows(rows, sortState) {
  const direction = sortState.sortDir === "asc" ? 1 : -1;
  const sortKey = sortState.sortKey || "maxWeightPercent";

  return rows.slice().sort((a, b) => {
    const aValue = sortValue(a, sortKey);
    const bValue = sortValue(b, sortKey);

    if (typeof aValue === "number" || typeof bValue === "number") {
      const result = compareNumbers(aValue, bValue);
      return result ? result * direction : a.symbol.localeCompare(b.symbol);
    }

    const result = String(aValue || "").localeCompare(String(bValue || ""));
    return (result || a.symbol.localeCompare(b.symbol)) * direction;
  });
}

function sortValue(row, sortKey) {
  if (sortKey.startsWith("source:")) {
    return row.weights[sortKey.slice("source:".length)] ?? 0;
  }
  return row[sortKey];
}

function compareNumbers(a, b) {
  const aNumber = typeof a === "number" && !Number.isNaN(a) ? a : null;
  const bNumber = typeof b === "number" && !Number.isNaN(b) ? b : null;

  if (aNumber == null && bNumber == null) return 0;
  if (aNumber == null) return -1;
  if (bNumber == null) return 1;
  return aNumber - bNumber;
}

function normalizeIndexSource(source) {
  const normalized = String(source || "")
    .trim()
    .replace(/[\s-]+/g, "_")
    .toLowerCase();

  const aliases = {
    binance_future: "binancefuture",
    binancefuture: "binancefuture",
    binancefutures: "binancefuture",
    binance_futures: "binancefuture",
    binance_perp: "binancefuture",
    binancealpha: "alpha",
    binance_alpha: "alpha",
    aster: "aster",
    gateio: "gate",
    gate_io: "gate",
    gate: "gate",
    mexc: "mexc",
    bybit: "bybit",
    bitget: "bitget",
    okex: "okex",
    okx: "okx",
    kucoin: "kucoin",
    pancakev3: "pancakev3",
    pancakeswapv3: "pancakev3",
    pancakeswap_v3: "pancakev3",
    pancakev2: "pancakev2",
    pancakeswapv2: "pancakev2",
    pancakeswap_v2: "pancakev2",
  };

  return aliases[normalized] || normalized;
}
