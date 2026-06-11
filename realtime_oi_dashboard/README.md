# Realtime OI Dashboard

本地网页项目，价格用 Binance Futures WebSocket 实时更新，OI 持仓按批次连续轮询。

## 启动

在仓库根目录运行：

```bash
./bin/python3 realtime_oi_dashboard/server.py
```

然后打开：

```text
http://127.0.0.1:8777
```

## 调整 OI 分批刷新

默认每 2 秒更新 10 个币，OI 请求会用 3 个 worker 小并发，24h ticker 会缓存 10 秒：

```bash
./bin/python3 realtime_oi_dashboard/server.py --oi-batch-size 10 --oi-batch-delay 2
```

更快一点可以每 1 秒更新 25 个币，同时保持 ticker 缓存，减少 `ticker/24hr` 触发限频：

```bash
./bin/python3 realtime_oi_dashboard/server.py --oi-batch-size 25 --oi-batch-delay 1 --oi-workers 3 --ticker-cache-seconds 10
```

如果遇到 `429` / `418`，先降速：

```bash
./bin/python3 realtime_oi_dashboard/server.py --oi-batch-size 10 --oi-batch-delay 2 --oi-workers 1 --ticker-cache-seconds 30
```

不建议高频更新全市场所有币，因为 Binance openInterest 和历史 OI 是按 symbol 请求，太高频容易触发限频。
