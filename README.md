# CryptoExchangeTicket

TradingView watchlist tools and Binance OI monitor.

## Run

Generate Binance watchlists and start the OI monitor:

```bash
python3 main.py
```

Run the Binance OI monitor directly:

```bash
python3 -m bn.binance_oi_monitor --interval-minutes 30 --alert-percent 5
```

Telegram config can be provided in `.env`:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```
