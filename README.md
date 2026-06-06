# CryptoExchangeTicket

TradingView watchlist tools and Binance OI monitor.

## Run

Generate Binance watchlists and start the OI monitor:

```bash
python3 main.py
```

Run the Binance OI monitor directly:

```bash
python3 -m exchanges.bn.binance_oi_monitor --interval-minutes 30 --alert-percent 5
```

Open the local ATH/ATL web page. It starts a background scanner automatically:

```bash
python3 -m ath_atl.web
```

You can still run one manual scan separately if needed:

```bash
python3 -m ath_atl.tracker
```

Outputs:

```text
ath_atl/data/ath_atl.db
ath_atl/data/ath_atl_snapshot.json
ath_atl/data/daily_breakouts.json
ath_atl/data/scan_status.json
ath_atl/logs/
```

The first run initializes ATH/ATL baselines in SQLite. Later runs compare new daily
klines against the stored ATH/ATL values and write `new_high` / `new_low`
breakouts to `ath_atl/data/daily_breakouts.json`.

Web pages:

```text
http://127.0.0.1:8788/
http://127.0.0.1:8788/breakouts
```

Small test run:

```bash
python3 -m ath_atl.web --market-types spot --symbols BTCUSDT
```

Telegram config can be provided in `.env`:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```
