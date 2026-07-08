export function formatNumber(value) {
  if (value == null || Number.isNaN(value)) return "-";
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export function formatCurrency(value) {
  if (value == null || Number.isNaN(value)) return "-";
  if (Math.abs(value) >= 100000000) return "$" + (value / 100000000).toFixed(2) + "亿";
  if (Math.abs(value) >= 10000) return "$" + (value / 10000).toFixed(2) + "万";
  return "$" + Number(value).toFixed(0);
}

export function formatPrice(value) {
  if (value == null || Number.isNaN(value)) return "-";
  return "$" + Number(value).toPrecision(6).replace(/\.?0+$/, "");
}

export function formatPercent(value) {
  if (value == null || Number.isNaN(value)) return "-";
  return (value >= 0 ? "+" : "") + Number(value).toFixed(2) + "%";
}

export function formatFundingRate(value) {
  if (value == null || Number.isNaN(value)) return "-";
  return (value >= 0 ? "+" : "") + Number(value).toFixed(4) + "%";
}

export function signClass(value) {
  return Number(value) >= 0 ? "pos" : "neg";
}

export function heatStyle(value, max) {
  if (value == null || Number.isNaN(value) || !max) return "";
  const ratio = Math.min(Math.abs(value) / max, 1);
  const alpha = 0.08 + ratio * 0.22;
  const color = Number(value) >= 0 ? "var(--green)" : "var(--red)";
  return `background: rgba(${color}, ${alpha});`;
}

const TRADINGVIEW_SYMBOL_MAP = {
  "币安人生USDT": "BIANRENSHENGUSDT",
  "龙虾USDT": "LONGXIAUSDT",
  "我踏马来了USDT": "WOTAMALAILIAOUSDT",
};

export function tradingViewUrl(symbol) {
  const tradingViewSymbol = TRADINGVIEW_SYMBOL_MAP[symbol] || symbol;
  return `https://www.tradingview.com/chart/n6rCV2e0/?symbol=BINANCE%3A${encodeURIComponent(tradingViewSymbol)}.P`;
}

export function binanceFuturesUrl(symbol) {
  return `https://www.binance.com/zh-CN/futures/${encodeURIComponent(symbol)}`;
}
