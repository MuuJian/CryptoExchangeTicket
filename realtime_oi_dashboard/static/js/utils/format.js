export function formatNumber(value) {
  const number = finiteNumber(value);
  if (number == null) return "-";
  return number.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export function formatCurrency(value) {
  const number = finiteNumber(value);
  if (number == null) return "-";
  if (Math.abs(number) >= 100000000) return "$" + (number / 100000000).toFixed(2) + "亿";
  if (Math.abs(number) >= 10000) return "$" + (number / 10000).toFixed(2) + "万";
  return "$" + number.toFixed(0);
}

export function formatPrice(value) {
  const number = finiteNumber(value);
  if (number == null) return "-";
  return "$" + number.toLocaleString(undefined, {
    maximumSignificantDigits: 6,
    useGrouping: Math.abs(number) >= 1000,
  });
}

export function formatPercent(value) {
  const number = finiteNumber(value);
  if (number == null) return "-";
  return (number >= 0 ? "+" : "") + number.toFixed(2) + "%";
}

export function formatFundingRate(value) {
  const number = finiteNumber(value);
  if (number == null) return "-";
  return (number >= 0 ? "+" : "") + number.toFixed(4) + "%";
}

export function signClass(value) {
  const number = finiteNumber(value);
  if (number == null) return "neutral";
  return number >= 0 ? "pos" : "neg";
}

export function heatStyle(value, max) {
  const number = finiteNumber(value);
  const maximum = finiteNumber(max);
  if (number == null || maximum == null || maximum <= 0) return "";
  const ratio = Math.min(Math.abs(number) / maximum, 1);
  const alpha = 0.08 + ratio * 0.22;
  const color = number >= 0 ? "var(--green)" : "var(--red)";
  return `background: rgba(${color}, ${alpha});`;
}

export function formatFundingTitle(nextFundingTime) {
  const time = finiteNumber(nextFundingTime);
  if (time == null || time <= 0) return "";
  return `下次资金费结算: ${new Date(time).toLocaleString()}`;
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

function finiteNumber(value) {
  if (value == null || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}
