# ATH / ATL Tracker

独立的 Binance 现货和合约 ATH/ATL 统计模块，不依赖也不污染 `exchanges/` 目录。

## 本地网页 + 后台扫描

```bash
python3 -m ath_atl.web
```

网页启动后会立即在后台跑一次 ATH/ATL 扫描，之后默认每 4 小时扫描一次。
页面会每 30 秒重新读取本地数据，扫描状态每 5 秒刷新一次。

如果想让后台扫描更频繁，可以调小间隔：

```bash
python3 -m ath_atl.web --scan-interval-hours 1
```

默认会同时扫描 4 个 symbol，比逐个扫快很多。如果 Binance 连接不稳定，可以降回单线程；如果网络很稳，可以提高一点：

```bash
python3 -m ath_atl.web --scan-workers 1
python3 -m ath_atl.web --scan-workers 8
```

如果遇到临时 SSL EOF / timeout，可以增加重试次数：

```bash
python3 -m ath_atl.web --retry-attempts 6 --retry-backoff 2
```

小范围测试可以只扫一个币：

```bash
python3 -m ath_atl.web --market-types spot --symbols BTCUSDT
```

只打开网页、不自动扫描：

```bash
python3 -m ath_atl.web --no-auto-scan
```

打开：

```text
http://127.0.0.1:8788/
```

## 手动扫描

如果你以后要接 crontab 或 Telegram，也可以单独跑扫描模块：

```bash
python3 -m ath_atl.tracker
```

## 本地数据

所有 ATH/ATL 相关运行数据都放在本目录下面：

```text
ath_atl/data/ath_atl.db
ath_atl/data/ath_atl_snapshot.json
ath_atl/data/daily_breakouts.json
ath_atl/data/scan_status.json
ath_atl/logs/
```
