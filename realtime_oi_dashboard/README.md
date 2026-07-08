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

默认每 1 秒更新 25 个币，OI 请求会用 3 个 worker 小并发。实时价格由浏览器 WebSocket 更新，不受 `--ticker-cache-seconds` 影响；这个缓存只用于后端 REST `/fapi/v1/ticker/24hr` 的 24h 汇总数据，例如 24h 成交额和 24h 价格变化。资金费率按 Binance 返回的 `nextFundingTime` 刷新：

```bash
./bin/python3 realtime_oi_dashboard/server.py
```

可以显式指定默认速度，同时保持 ticker 和资金费率缓存，减少触发限频：

```bash
./bin/python3 realtime_oi_dashboard/server.py --oi-batch-size 25 --oi-batch-delay 1 --oi-workers 3 --ticker-cache-seconds 10 --funding-cache-seconds 3600
```

`--funding-cache-seconds` 现在只作为 `nextFundingTime` 缺失时的兜底缓存时间；正常情况下会在下一次资金费结算时间后刷新。

如果遇到 `429` / `418`，先降速：

```bash
./bin/python3 realtime_oi_dashboard/server.py --oi-batch-size 10 --oi-batch-delay 2 --oi-workers 1 --ticker-cache-seconds 30 --funding-cache-seconds 3600
```

不建议高频更新全市场所有币，因为 Binance openInterest 和历史 OI 是按 symbol 请求，太高频容易触发限频。
