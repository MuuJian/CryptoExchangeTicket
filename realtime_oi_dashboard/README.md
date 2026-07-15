# Realtime OI Dashboard

本地 Binance Futures 面板。价格由浏览器 WebSocket 实时更新；服务端分批轮询当前 OI、历史 OI、24 小时行情与资金费率。

## 启动

在仓库根目录运行：

```bash
python3 -m realtime_oi_dashboard.server
```

打开 <http://127.0.0.1:8777>。

默认每秒更新 25 个交易对，并使用 3 个 OI worker。资金费率正常情况下会在 Binance 返回的下一次结算时间后刷新；`--funding-cache-seconds` 只在结算时间缺失时作为兜底。

限频时可以降速：

```bash
python3 -m realtime_oi_dashboard.server \
  --oi-batch-size 10 \
  --oi-batch-delay 2 \
  --oi-workers 1 \
  --ticker-cache-seconds 30
```

页面只显示本次启动后刚获取的数据，并按批次逐步填充。服务会读取上次快照作为 OI 变化的比较基准，但不会直接把旧行显示出来。基准快照默认每 10 秒原子写入 `data/latest_oi.json`，可用 `--snapshot-save-interval` 调整间隔。
