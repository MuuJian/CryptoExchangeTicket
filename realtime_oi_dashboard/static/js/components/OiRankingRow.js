import {
  formatCurrency,
  formatPercent,
  formatPrice,
  heatStyle,
  signClass,
  tradingViewUrl,
} from "../utils/format.js";

export function createRankingRow(row, context) {
  const tr = document.createElement("tr");
  tr.dataset.symbol = row.symbol;

  const favoriteCell = document.createElement("td");
  favoriteCell.className = "favorite-cell";
  const favoriteButton = document.createElement("button");
  favoriteButton.className = "favorite-btn";
  favoriteButton.type = "button";
  favoriteButton.textContent = "★";
  favoriteCell.append(favoriteButton);

  const symbolCell = document.createElement("td");
  symbolCell.className = "symbol";
  const symbolLink = document.createElement("a");
  symbolLink.className = "symbol-link";
  symbolLink.target = "_blank";
  symbolLink.rel = "noopener noreferrer";
  symbolCell.append(symbolLink);

  const priceCell = document.createElement("td");
  const priceChangeCell = document.createElement("td");
  const oiValueCell = document.createElement("td");
  const volumeCell = document.createElement("td");
  const oiChangeCell = document.createElement("td");
  const oi24hChangeCell = document.createElement("td");
  const oi7dChangeCell = document.createElement("td");
  const changeValueCell = document.createElement("td");

  tr.append(
    favoriteCell,
    symbolCell,
    priceCell,
    priceChangeCell,
    oiValueCell,
    volumeCell,
    oiChangeCell,
    oi24hChangeCell,
    oi7dChangeCell,
    changeValueCell,
  );

  tr._cells = {
    favoriteButton,
    symbolLink,
    priceCell,
    priceChangeCell,
    oiValueCell,
    volumeCell,
    oiChangeCell,
    oi24hChangeCell,
    oi7dChangeCell,
    changeValueCell,
  };

  updateRankingRow(tr, row, context);
  return tr;
}

export function updateRankingRow(tr, row, context) {
  const cells = tr._cells;
  const isFavorite = context.favorites.has(row.symbol);

  cells.favoriteButton.dataset.favorite = row.symbol;
  cells.favoriteButton.classList.toggle("active", isFavorite);
  cells.favoriteButton.title = isFavorite ? "取消收藏" : "加入收藏";

  cells.symbolLink.href = tradingViewUrl(row.symbol);
  cells.symbolLink.textContent = row.symbol;
  cells.priceCell.textContent = formatPrice(row.price);
  cells.oiValueCell.textContent = formatCurrency(row.currentOiValue);
  cells.volumeCell.textContent = formatCurrency(row.volume24h);
  cells.changeValueCell.textContent = formatCurrency(row.changeValue);

  updateHeatCell(
    cells.priceChangeCell,
    row.priceChangePercent,
    context.heatMax.priceChangePercent,
  );
  updateHeatCell(cells.oiChangeCell, row.changePercent, context.heatMax.changePercent);
  updateHeatCell(
    cells.oi24hChangeCell,
    row.oi24hChangePercent,
    context.heatMax.oi24hChangePercent,
  );
  updateHeatCell(
    cells.oi7dChangeCell,
    row.oi7dChangePercent,
    context.heatMax.oi7dChangePercent,
  );
}

function updateHeatCell(cell, value, max) {
  cell.className = `heat ${signClass(value)}`;
  cell.style.cssText = heatStyle(value, max);
  cell.textContent = formatPercent(value);
}
