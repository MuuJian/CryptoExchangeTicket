import { formatPercent } from "../utils/format.js";

export function renderStatCards(elements, stats) {
  elements.changeCount.textContent = stats.changeCount;
  elements.topIncrease.textContent = stats.topIncrease?.symbol || "-";
  elements.topIncreaseNote.textContent = formatPercent(stats.topIncrease?.oi24hChangePercent);
  elements.topDecrease.textContent = stats.topDecrease?.symbol || "-";
  elements.topDecreaseNote.textContent = formatPercent(stats.topDecrease?.oi24hChangePercent);
}

export function renderWsState(element, value) {
  element.textContent = value;
}
