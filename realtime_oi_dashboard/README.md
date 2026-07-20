# Realtime OI Dashboard

本地 Binance Futures 面板。价格由浏览器 WebSocket 实时更新；服务端分批轮询当前 OI、历史 OI、24 小时行情与资金费率。

WebSocket 断线时会清空旧的实时价格缓存，下一次 OI 快照会自动改用服务端行情，重连后再恢复实时价格。

## 代码结构

- `poller.py`：Binance 请求、批次轮询、缓存与快照。
- `server.py`：命令行参数、本地 HTTP 服务与启动/停止流程。
- `static/`：浏览器端价格 WebSocket、筛选、排序与页面渲染。

## 启动

在仓库根目录运行：

```bash
.venv/bin/python -m realtime_oi_dashboard.server
```

打开 <http://127.0.0.1:8777>。

默认每批更新 25 个交易对，批次之间等待 1 秒，并使用 3 个 OI worker。资金费率正常情况下会在 Binance 返回的下一次结算时间后刷新；`--funding-cache-seconds` 只在结算时间缺失时作为兜底，已经过去的结算时间不会继续显示。

限频时可以降速：

```bash
.venv/bin/python -m realtime_oi_dashboard.server \
  --oi-batch-size 10 \
  --oi-batch-delay 2 \
  --oi-workers 1 \
  --ticker-cache-seconds 30
```

页面只显示本次启动后刚获取的数据，并按批次逐步填充。默认每批轮询 25 个交易对，批次完成后等待 1 秒；约 530 个交易对完整一轮至少需要二十多秒，实际还要加上接口耗时。服务只会把最近 15 分钟内的旧快照用作重启后的比较基准；这 15 分钟不是刷新间隔，更早的基准不会混入实时变化，也不会直接显示旧行。基准快照默认每 10 秒原子写入 `data/latest_oi.json`，可用 `--snapshot-save-interval` 调整间隔；正常停止时还会保存一次最后完成的批次。

表格里的“持仓变化”比较同一合约本次与上次成功轮询的 OI，正常情况下约每个完整轮询周期更新一次；服务重启后的第一次变化才会使用上面所说的最近 15 分钟基线。

24 小时和 7 天变化按历史记录的真实时间戳匹配。目标时间附近两小时内没有可用记录时显示 `-`，不会用错误跨度的数据代替。
