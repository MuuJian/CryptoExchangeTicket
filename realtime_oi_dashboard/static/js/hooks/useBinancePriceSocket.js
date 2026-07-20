export function useBinancePriceSocket({ onStatusChange, onPricesChange }) {
  const priceMap = new Map();
  const pendingSymbols = new Set();
  let socket = null;
  let reconnectTimer = 0;
  let flushFrame = 0;
  let stopped = false;
  let reconnectAttempts = 0;

  function connect() {
    stopped = false;
    window.clearTimeout(reconnectTimer);
    reconnectTimer = 0;

    const previousSocket = socket;
    socket = null;
    clearLivePrices();
    if (previousSocket && previousSocket.readyState < WebSocket.CLOSING) {
      previousSocket.close();
    }

    const url = "wss://fstream.binance.com/market/stream?streams=!ticker@arr";
    let nextSocket;
    try {
      nextSocket = new WebSocket(url);
    } catch {
      onStatusChange("异常");
      scheduleReconnect();
      return;
    }
    socket = nextSocket;
    onStatusChange("连接中");

    nextSocket.onopen = () => {
      if (socket !== nextSocket || stopped) return;
      onStatusChange("实时");
    };

    nextSocket.onmessage = event => {
      if (socket !== nextSocket || stopped) return;

      let payload;
      try {
        payload = JSON.parse(event.data);
      } catch {
        return;
      }
      if (!payload || typeof payload !== "object" || !Array.isArray(payload.data)) return;
      reconnectAttempts = 0;

      const list = payload.data;
      for (const item of list) {
        if (
          !item
          || typeof item.s !== "string"
          || !item.s.trim()
          || item.s !== item.s.trim()
          || item.st !== 1
        ) continue;

        const price = finiteNumber(item.c);
        if (price == null || price <= 0) continue;

        const volume24h = finiteNumber(item.q);
        const priceChangePercent = finiteNumber(item.P);
        const next = {
          price,
          volume24h: volume24h != null && volume24h >= 0
            ? volume24h
            : undefined,
          priceChangePercent: priceChangePercent != null
            ? priceChangePercent
            : undefined,
        };
        const prev = priceMap.get(item.s);

        if (
          !prev
          || prev.price !== next.price
          || prev.volume24h !== next.volume24h
          || prev.priceChangePercent !== next.priceChangePercent
        ) {
          priceMap.set(item.s, next);
          pendingSymbols.add(item.s);
        }
      }

      if (pendingSymbols.size) scheduleFlush();
    };

    nextSocket.onclose = () => {
      if (socket !== nextSocket) return;
      socket = null;
      clearLivePrices();
      if (stopped) return;
      scheduleReconnect();
    };

    nextSocket.onerror = () => {
      if (socket !== nextSocket || stopped) return;
      onStatusChange("异常");
      nextSocket.close();
    };
  }

  function scheduleReconnect() {
    if (stopped || reconnectTimer) return;
    onStatusChange("重连中");
    reconnectAttempts += 1;
    const delay = Math.min(1000 * 2 ** (reconnectAttempts - 1), 30000);
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = 0;
      connect();
    }, delay);
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
    window.clearTimeout(reconnectTimer);
    reconnectTimer = 0;

    const currentSocket = socket;
    socket = null;
    clearLivePrices();
    if (currentSocket && currentSocket.readyState < WebSocket.CLOSING) {
      currentSocket.close();
    }
  }

  function clearLivePrices() {
    priceMap.clear();
    pendingSymbols.clear();
    if (flushFrame) {
      window.cancelAnimationFrame(flushFrame);
      flushFrame = 0;
    }
  }

  return {
    connect,
    close,
    getPrices() {
      return priceMap;
    },
  };
}

function finiteNumber(value) {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value !== "string" || !value.trim()) return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}
