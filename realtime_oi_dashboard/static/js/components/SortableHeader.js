export function createSortableHeaders({ headers, sort, onChange }) {
  headers.forEach(th => {
    th.tabIndex = 0;
    th.addEventListener("click", () => activate(th));
    th.addEventListener("keydown", event => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      activate(th);
    });
  });

  function activate(th) {
    sort.setSortKey(th.dataset.sort);
    render();
    onChange();
  }

  function render() {
    const state = sort.getState();
    headers.forEach(th => {
      th.classList.remove("sorted-asc", "sorted-desc");
      th.setAttribute("aria-sort", "none");
      if (th.dataset.sort === state.sortKey) {
        th.classList.add(state.sortDir === "asc" ? "sorted-asc" : "sorted-desc");
        th.setAttribute(
          "aria-sort",
          state.sortDir === "asc" ? "ascending" : "descending",
        );
      }
    });
  }

  return { render };
}
