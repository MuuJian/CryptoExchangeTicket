export function createFilterBar({ elements, filters, favorites, onChange }) {
  elements.searchInput.addEventListener("input", () => {
    if (filters.setQuery(elements.searchInput.value.trim().toUpperCase())) onChange();
  });

  elements.limitSelect.addEventListener("change", () => {
    if (filters.setLimit(elements.limitSelect.value)) onChange();
  });

  elements.oiValueFilter.addEventListener("change", () => {
    if (filters.setMinOiValue(elements.oiValueFilter.value)) onChange();
  });

  elements.volumeFilter.addEventListener("change", () => {
    if (filters.setMinVolume(elements.volumeFilter.value)) onChange();
  });

  elements.favoritesOnlyBtn.addEventListener("click", () => {
    filters.toggleFavoritesOnly();
    render();
    onChange();
  });

  function render() {
    const state = filters.getState();
    elements.favoritesOnlyBtn.classList.toggle("active", state.favoritesOnly);
    elements.favoritesOnlyBtn.setAttribute(
      "aria-pressed",
      String(state.favoritesOnly),
    );
    elements.favoritesOnlyBtn.textContent = state.favoritesOnly
      ? `收藏 ${favorites.size}`
      : "只看收藏";
  }

  return { render };
}
