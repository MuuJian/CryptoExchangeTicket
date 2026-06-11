export function useTableFilters(initialState = {}) {
  const state = {
    query: "",
    limit: 99999,
    minOiValue: 0,
    minVolume: 0,
    favoritesOnly: false,
    ...initialState,
  };
  let version = 0;

  function update(nextState) {
    let changed = false;
    for (const [key, value] of Object.entries(nextState)) {
      if (state[key] !== value) {
        state[key] = value;
        changed = true;
      }
    }
    if (changed) version += 1;
    return changed;
  }

  return {
    setQuery(query) {
      return update({ query });
    },
    setLimit(limit) {
      return update({ limit: Number(limit) });
    },
    setMinOiValue(minOiValue) {
      return update({ minOiValue: Number(minOiValue) });
    },
    setMinVolume(minVolume) {
      return update({ minVolume: Number(minVolume) });
    },
    toggleFavoritesOnly() {
      return update({ favoritesOnly: !state.favoritesOnly });
    },
    getState() {
      return state;
    },
    getVersion() {
      return version;
    },
  };
}
