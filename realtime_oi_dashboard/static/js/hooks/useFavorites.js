export function useFavorites(storageKey) {
  let favorites = readFavorites(storageKey);
  let version = 0;

  function save() {
    try {
      localStorage.setItem(storageKey, JSON.stringify([...favorites]));
    } catch {
      // Favorites still work for the current page when storage is unavailable.
    }
  }

  function toggle(symbol) {
    if (favorites.has(symbol)) {
      favorites.delete(symbol);
    } else {
      favorites.add(symbol);
    }
    version += 1;
    save();
  }

  return {
    has(symbol) {
      return favorites.has(symbol);
    },
    toggle,
    getSet() {
      return favorites;
    },
    getVersion() {
      return version;
    },
    get size() {
      return favorites.size;
    },
  };
}

function readFavorites(storageKey) {
  try {
    const raw = JSON.parse(localStorage.getItem(storageKey) || "[]");
    return new Set(Array.isArray(raw) ? raw : []);
  } catch {
    return new Set();
  }
}
