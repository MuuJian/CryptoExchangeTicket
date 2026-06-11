const PRICE_DRIVEN_SORT_KEYS = new Set([
  "price",
  "priceChangePercent",
  "currentOiValue",
  "volume24h",
  "changeValue",
]);

export function sortableNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

export function applyLivePriceToRow(row, live) {
  if (!row || !live || !Number.isFinite(live.price)) return false;

  let changed = false;
  const price = live.price;
  const volume24h = Number.isFinite(live.volume24h) ? live.volume24h : undefined;

  if (row.price !== price) {
    row.price = price;
    changed = true;
  }

  const price24hAgo = Number(row.price24hAgo);
  const priceChangePercent = price24hAgo > 0
    ? (price - price24hAgo) / price24hAgo * 100
    : row.priceChangePercent;

  if (row.priceChangePercent !== priceChangePercent) {
    row.priceChangePercent = priceChangePercent;
    changed = true;
  }

  const currentOi = Number(row.currentOi);
  if (Number.isFinite(currentOi)) {
    const currentOiValue = currentOi * price;
    if (row.currentOiValue !== currentOiValue) {
      row.currentOiValue = currentOiValue;
      changed = true;
    }
  }

  if (volume24h !== undefined && row.volume24h !== volume24h) {
    row.volume24h = volume24h;
    changed = true;
  }

  changed = patchChangeValue(row, "changeAmount", "changeValue", price) || changed;
  changed = patchChangeValue(row, "oi24hChangeAmount", "oi24hChangeValue", price) || changed;
  changed = patchChangeValue(row, "oi7dChangeAmount", "oi7dChangeValue", price) || changed;

  return changed;
}

export function filterRankingRows(rows, filters, favorites) {
  const query = filters.query.trim().toUpperCase();
  const minOiValue = Number(filters.minOiValue || 0);
  const minVolume = Number(filters.minVolume || 0);

  return rows.filter(row => {
    if (query && !row.symbol.includes(query)) return false;
    if (filters.favoritesOnly && !favorites.has(row.symbol)) return false;
    if (minOiValue && Number(row.currentOiValue || 0) < minOiValue) return false;
    if (minVolume && Number(row.volume24h || 0) < minVolume) return false;
    return true;
  });
}

export function sortRankingRows(rows, sortState) {
  const dir = sortState.sortDir === "asc" ? 1 : -1;
  const sorted = rows.slice();

  sorted.sort((a, b) => {
    if (sortState.sortKey === "symbol") return a.symbol.localeCompare(b.symbol) * dir;

    const left = sortableNumber(a[sortState.sortKey]);
    const right = sortableNumber(b[sortState.sortKey]);
    if (left == null && right == null) return 0;
    if (left == null) return 1;
    if (right == null) return -1;
    return (left - right) * dir;
  });

  return sorted;
}

export function buildVisibleRows(rows, filters, sortState, favorites) {
  return sortRankingRows(filterRankingRows(rows, filters, favorites), sortState)
    .slice(0, Number(filters.limit || 99999));
}

export function getHeatMax(rows) {
  return {
    priceChangePercent: maxAbs(rows, "priceChangePercent"),
    changePercent: maxAbs(rows, "changePercent"),
    oi24hChangePercent: maxAbs(rows, "oi24hChangePercent"),
    oi7dChangePercent: maxAbs(rows, "oi7dChangePercent"),
  };
}

export function isPriceDrivenView(filters, sortState) {
  return PRICE_DRIVEN_SORT_KEYS.has(sortState.sortKey)
    || Number(filters.minOiValue || 0) > 0
    || Number(filters.minVolume || 0) > 0;
}

function patchChangeValue(row, amountKey, valueKey, price) {
  if (row[amountKey] == null) return false;
  const nextValue = row[amountKey] * price;
  if (row[valueKey] === nextValue) return false;
  row[valueKey] = nextValue;
  return true;
}

function maxAbs(rows, key) {
  return Math.max(...rows.map(row => Math.abs(row[key] || 0)), 0);
}
