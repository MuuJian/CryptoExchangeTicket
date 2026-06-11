export function useBinancePriceSocket({ onStatusChange, onPricesChange }) {
  const priceMap = new Map();
  const pendingSymbols = new Set();
  let socket = null;
  let reconnectTimer = 0;
  let flushFrame = 0;
  let stopped = false;

  function connect() {
    stopped = false;
    clearTimeout(reconnectTimer);

    const url = "wss://fstream.binance.com/stream?streams=!ticker@arr";
    socket = new WebSocket(url);
    onStatusChange("Connecting");

    socket.onopen = () => {
      onStatusChange("Live");
    };

    socket.onmessage = event => {
      let payload;
      try {
        payload = JSON.parse(event.data);
      } catch {
        return;
      }

      const list = Array.isArray(payload.data) ? payload.data : [];
      for (const item of list) {
        if (!item || !item.s) continue;

        const price = Number(item.c);
        if (!Number.isFinite(price)) continue;

        const volume24h = Number(item.q);
        const next = {
          price,
          volume24h: Number.isFinite(volume24h) ? volume24h : undefined,
        };
        const prev = priceMap.get(item.s);

        if (!prev || prev.price !== next.price || prev.volume24h !== next.volume24h) {
          priceMap.set(item.s, next);
          pendingSymbols.add(item.s);
        }
      }

      scheduleFlush();
    };

    socket.onclose = () => {
      if (stopped) return;
      onStatusChange("Reconnecting");
      reconnectTimer = window.setTimeout(connect, 2000);
    };

    socket.onerror = () => {
      onStatusChange("Error");
      socket.close();
    };
  }

  function scheduleFlush() {
    if (flushFrame) return;
    flushFrame = window.requestAnimationFrame(() => {
      flushFrame = 0;
      if (!pendingSymbols.size) return;

      const changedSymbols = new Set(pendingSymbols);
      pendingSymbols.clear();
      onPricesChange(changedSymbols, priceMap);
    });
  }

  function close() {
    stopped = true;
    clearTimeout(reconnectTimer);
    if (flushFrame) window.cancelAnimationFrame(flushFrame);
    if (socket) socket.close();
  }

  return {
    connect,
    close,
    getPrices() {
      return priceMap;
    },
  };
}
