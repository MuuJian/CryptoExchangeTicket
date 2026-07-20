# CryptoExchangeTicket

生成 Binance TradingView 观察列表，并提供 Futures 实时持仓变化面板。

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

结果写入 `exchange_ticket/ticket/`，单个文件最多 500 行；重复项会自动去除，旧的多余分片会自动清理：

- `binance_usdt_pairs.txt`：加密货币现货
- `binance_futures_pairs.txt`：加密货币永续合约
- `binance_tradfi_spot_pairs.txt`：TradFi 现货
- `binance_tradfi_futures_pairs.txt`：TradFi 永续合约

TradFi 现货会根据当前 TradFi 期货的基础资产加 `B` 后，与实际在交易的现货自动匹配，无需维护手工名单。
请求失败、返回空名单或缺少任一市场分类时，程序会退出，对应的旧文件不会被空结果覆盖。

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

更多参数可用 `.venv/bin/python -m realtime_oi_dashboard.server --help` 查看。

## 前端语法检查

需要 Node.js；同时检查 JavaScript 语法、相对导入、入口可达性以及页面 ID：

```bash
node realtime_oi_dashboard/scripts/check-static-js.mjs
```

## 目录

```text
exchange_ticket/          Binance 观察列表生成器
realtime_oi_dashboard/    实时价格和 OI 面板
shared/http.py            OI 面板共用的 JSON 请求、重试和线程会话
shared/utils.py           名单写入、数值解析和快照原子写入
shared/web.py             OI 面板的静态文件和 JSON 响应处理
```
