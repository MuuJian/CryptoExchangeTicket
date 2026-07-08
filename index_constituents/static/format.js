export function formatWeightPercent(value) {
  if (value == null || Number.isNaN(value)) return "0%";
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: 2,
  }) + "%";
}

export function binanceFuturesUrl(symbol) {
  return `https://www.binance.com/zh-CN/futures/${encodeURIComponent(symbol)}`;
}
