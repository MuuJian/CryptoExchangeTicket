export function createSortableHeaders({ headers, sort, onChange }) {
  headers.forEach(th => {
    th.addEventListener("click", () => {
      sort.setSortKey(th.dataset.sort);
      render();
      onChange();
    });
  });

  function render() {
    const state = sort.getState();
    headers.forEach(th => {
      th.classList.remove("sorted-asc", "sorted-desc");
      if (th.dataset.sort === state.sortKey) {
        th.classList.add(state.sortDir === "asc" ? "sorted-asc" : "sorted-desc");
      }
    });
  }

  return { render };
}
