export function useTableSort(initialState = {}) {
  const state = {
    sortKey: "changePercent",
    sortDir: "desc",
    ...initialState,
  };
  let version = 0;

  function setSortKey(sortKey) {
    if (state.sortKey === sortKey) {
      state.sortDir = state.sortDir === "desc" ? "asc" : "desc";
    } else {
      state.sortKey = sortKey;
      state.sortDir = "desc";
    }
    version += 1;
  }

  return {
    setSortKey,
    getState() {
      return state;
    },
    getVersion() {
      return version;
    },
  };
}
