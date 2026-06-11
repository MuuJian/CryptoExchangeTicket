import { createRankingRow, updateRankingRow } from "./OiRankingRow.js";

const EMPTY_MESSAGE = "正在建立 OI 基准。分批更新一圈后，持仓变化会逐步出现。";

export function createOiRankingTable({ tbody, getRowBySymbol }) {
  const rowsBySymbol = new Map();
  const visibleSymbols = new Set();

  function render(rows, context) {
    visibleSymbols.clear();

    if (!rows.length) {
      rowsBySymbol.clear();
      tbody.textContent = "";
      tbody.append(createEmptyRow());
      return;
    }

    const fragment = document.createDocumentFragment();
    const nextVisible = new Set();

    for (const row of rows) {
      nextVisible.add(row.symbol);
      visibleSymbols.add(row.symbol);

      let tr = rowsBySymbol.get(row.symbol);
      if (!tr) {
        tr = createRankingRow(row, context);
        rowsBySymbol.set(row.symbol, tr);
      } else {
        updateRankingRow(tr, row, context);
      }
      fragment.append(tr);
    }

    for (const [symbol, tr] of rowsBySymbol.entries()) {
      if (!nextVisible.has(symbol)) {
        tr.remove();
        rowsBySymbol.delete(symbol);
      }
    }

    tbody.textContent = "";
    tbody.append(fragment);
  }

  function patchRows(symbols, context) {
    for (const symbol of symbols) {
      if (!visibleSymbols.has(symbol)) continue;

      const tr = rowsBySymbol.get(symbol);
      const row = getRowBySymbol(symbol);
      if (tr && row) updateRankingRow(tr, row, context);
    }
  }

  function createEmptyRow() {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 10;
    td.className = "empty";
    td.textContent = EMPTY_MESSAGE;
    tr.append(td);
    return tr;
  }

  return {
    render,
    patchRows,
    hasVisibleSymbol(symbol) {
      return visibleSymbols.has(symbol);
    },
  };
}
