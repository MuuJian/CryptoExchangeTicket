import assert from "node:assert/strict";

import {
  formatCurrency,
  formatPercent,
  formatPrice,
  signClass,
} from "../static/js/utils/format.js";
import {
  applyLivePriceToRow,
  buildHighOi7dRows,
  buildVisibleRows,
} from "../static/js/utils/rankingRows.js";

assert.notEqual(formatPrice(100000), "$1", "whole prices must keep trailing zeroes");
assert.equal(formatPrice(null), "-");
assert.equal(formatCurrency(Number.NaN), "-");
assert.equal(formatPercent(1.234), "+1.23%");
assert.equal(signClass(null), "neutral");

const row = {
  symbol: "BTCUSDT",
  price: 100,
  currentOi: 2,
  currentOiValue: 200,
  changeAmount: 1,
  changeValue: 100,
};
assert.equal(applyLivePriceToRow(row, { price: 120, volume24h: 1000 }), true);
assert.equal(row.currentOiValue, 240);
assert.equal(row.changeValue, 120);

const visible = buildVisibleRows(
  [
    { symbol: "ETHUSDT", currentOiValue: 100 },
    { symbol: "BTCUSDT", currentOiValue: 200 },
  ],
  { query: "btc", limit: 10, minOiValue: 0, minVolume: 0, favoritesOnly: false },
  { sortKey: "currentOiValue", sortDir: "desc" },
  new Set(),
);
assert.deepEqual(visible.map(item => item.symbol), ["BTCUSDT"]);
assert.deepEqual(
  buildHighOi7dRows([
    { symbol: "A", oi7dChangePercent: 101, currentOiValue: 10000001 },
    { symbol: "B", oi7dChangePercent: 99, currentOiValue: 20000000 },
  ]).map(item => item.symbol),
  ["A"],
);

console.log("Dashboard JavaScript unit checks passed.");
