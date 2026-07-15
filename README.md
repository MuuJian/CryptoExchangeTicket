# CryptoExchangeTicket

生成 TradingView 观察列表，并提供 Binance Futures 实时持仓变化面板。

## 安装

需要 Python 3.10 或更高版本：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## 生成观察列表

默认生成 Binance 现货与永续合约列表：

```bash
.venv/bin/python main.py
```

也可以指定交易所和市场：

```bash
.venv/bin/python main.py --exchange bybit --market futures
.venv/bin/python main.py --exchange all --market spot
```

支持 `binance`、`bybit`、`bitget` 和 `okx`。结果写入 `exchange_ticket/ticket/`，单个文件最多 500 行；重复项会自动去除，旧的多余分片会自动清理。Binance 的 TradFi 现货与合约会合并写入 `binance_tradfi_pairs.txt`。

## 实时 OI 面板

```bash
.venv/bin/python -m realtime_oi_dashboard.server
```

打开 <http://127.0.0.1:8777>。浏览器通过 Binance Futures WebSocket 更新价格，服务端分批获取 OI、24 小时/7 天 OI 变化和资金费率。

如果遇到 Binance `429` 或 `418` 限频，可以降低请求速度：

```bash
.venv/bin/python -m realtime_oi_dashboard.server \
  --oi-batch-size 10 \
  --oi-batch-delay 2 \
  --oi-workers 1 \
  --ticker-cache-seconds 30
```

更多参数可用 `python -m realtime_oi_dashboard.server --help` 查看。

## 验证

`tests/` 是开发时使用的自动检查，不参与程序运行。建议保留它，以便修改观察列表或 OI 逻辑后快速确认功能没有被改坏。

Python 测试不需要访问网络：

```bash
.venv/bin/python -m unittest discover -v
```

前端检查需要 Node.js：

```bash
node realtime_oi_dashboard/scripts/check-static-js.mjs
node realtime_oi_dashboard/scripts/test-static-js.mjs
```

## 目录

```text
exchange_ticket/          交易所观察列表与共享 HTTP/Web 工具
realtime_oi_dashboard/    实时价格和 OI 面板
tests/                    离线单元测试
```
