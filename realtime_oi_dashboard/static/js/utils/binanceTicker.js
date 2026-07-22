const USD_M_SYMBOL_TYPE = 1;

export function parseUsdMMarketTickerMessage(data) {
  let payload;
  try {
    payload = JSON.parse(data);
  } catch {
    return [];
  }

  const items = Array.isArray(payload) ? payload : payload?.data;
  if (!Array.isArray(items)) return [];

  const updates = [];
  for (const item of items) {
    const update = normalizeTicker(item);
    if (update) updates.push(update);
  }
  return updates;
}

export function mergeTickerUpdate(previous, next) {
  return {
    price: next.price,
    volume24h: next.volume24h ?? previous?.volume24h,
    priceChangePercent:
      next.priceChangePercent ?? previous?.priceChangePercent,
  };
}

function normalizeTicker(item) {
  if (
    !item
    || typeof item !== "object"
    || typeof item.s !== "string"
    || !item.s.trim()
    || item.s !== item.s.trim()
    || (item.st !== undefined && item.st !== USD_M_SYMBOL_TYPE)
  ) return null;

  const price = finiteNumber(item.c);
  if (price == null || price <= 0) return null;

  const volume24h = finiteNumber(item.q);
  const priceChangePercent = finiteNumber(item.P);
  return {
    symbol: item.s,
    ticker: {
      price,
      volume24h: volume24h != null && volume24h >= 0
        ? volume24h
        : undefined,
      priceChangePercent: priceChangePercent != null
        ? priceChangePercent
        : undefined,
    },
  };
}

function finiteNumber(value) {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value !== "string" || !value.trim()) return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}
