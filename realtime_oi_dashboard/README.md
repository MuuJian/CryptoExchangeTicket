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

默认每 1 秒更新 25 个币：

```bash
./bin/python3 realtime_oi_dashboard/server.py --oi-batch-size 25 --oi-batch-delay 1
```

更快一点可以每秒更新 50 个币：

```bash
./bin/python3 realtime_oi_dashboard/server.py --oi-batch-size 50 --oi-batch-delay 1
```

不建议每秒更新全市场所有币，因为 Binance openInterest 是按 symbol 请求，太高频容易触发限频。
