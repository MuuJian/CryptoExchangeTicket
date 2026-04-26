import argparse
import json
import os
import time
from datetime import datetime

try:
    import requests
except ModuleNotFoundError:
    requests = None


def load_env_file(file_path=".env"):
    if not os.path.exists(file_path):
        return

    with open(file_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line: #注释或空行或不合法的行都跳过
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


class TelegramNotifier:
    def __init__(self, bot_token=None, chat_id=None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token and chat_id)

    def send(self, message, parse_mode=None):
        if not self.enabled:
            return
        if requests is None:
            print("Telegram 推送失敗: requests 尚未安裝")
            return

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            print(f"Telegram 推送失敗: {e}")


class BinanceOIMonitor:
    def __init__(
        self,
        alert_percent=10.0,
        notifier=None,
        snapshot_file="ticket/bnoi_latest_snapshot.json",
    ):
        self.base_url = "https://fapi.binance.com"
        self.info_url = f"{self.base_url}/fapi/v1/exchangeInfo"
        self.oi_url = f"{self.base_url}/fapi/v1/openInterest"
        self.price_url = f"{self.base_url}/fapi/v1/ticker/price"
        self.alert_percent = alert_percent
        self.notifier = notifier or TelegramNotifier()
        self.session = requests.Session() if requests else None
        self.snapshot_file = snapshot_file
        self.previous_snapshot = self.load_latest_snapshot()

    def load_latest_snapshot(self):
        if not os.path.exists(self.snapshot_file):
            return {}

        try:
            with open(self.snapshot_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
            data = payload.get("data", {})
            if isinstance(data, dict):
                print(f"{now()} 已載入上一輪快照: {self.snapshot_file}")
                return data
        except Exception as e:
            print(f"讀取上一輪快照失敗: {e}")

        return {}

    def save_snapshot(self, snapshot):
        payload = {
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "data": snapshot,
        }
        folder = os.path.dirname(self.snapshot_file)
        if folder:
            os.makedirs(folder, exist_ok=True)

        temp_file = f"{self.snapshot_file}.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.replace(temp_file, self.snapshot_file)

    def get_active_symbols(self):
        try:
            resp = self.session.get(self.info_url, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            return [
                item["symbol"]
                for item in data.get("symbols", [])
                if item.get("quoteAsset") == "USDT"
                and item.get("status") == "TRADING"
                and item.get("contractType") == "PERPETUAL"
            ]
        except Exception as e:
            print(f"獲取合約列表失敗: {e}")
            return []

    def get_open_interest(self, symbol):
        try:
            resp = self.session.get(self.oi_url, params={"symbol": symbol}, timeout=8)
            resp.raise_for_status()
            data = resp.json()
            return float(data["openInterest"])
        except Exception as e:
            print(f"{symbol} OI 獲取失敗: {e}")
            return None

    def get_price(self, symbol):
        try:
            resp = self.session.get(self.price_url, params={"symbol": symbol}, timeout=8)
            resp.raise_for_status()
            data = resp.json()
            return float(data["price"])
        except Exception:
            return None

    def collect_interval_changes(self):
        symbols = self.get_active_symbols()
        if not symbols:
            return []

        print(f"{now()} 掃描 {len(symbols)} 個 USDT 永續合約...")
        current_snapshot = {}
        changes = []

        for index, symbol in enumerate(symbols, 1):
            current_oi = self.get_open_interest(symbol)
            price = self.get_price(symbol)
            if current_oi is None:
                continue

            current_snapshot[symbol] = {
                "oi": current_oi,
                "price": price,
            }

            previous_item = self.previous_snapshot.get(symbol)
            if not previous_item or previous_item["oi"] <= 0:
                continue

            previous_oi = previous_item["oi"]
            previous_price = previous_item["price"]
            current_oi_usdt = current_oi * price if price else None
            change_percent = (current_oi - previous_oi) / previous_oi * 100
            price_change_percent = None
            if price is not None and previous_price is not None and previous_price > 0:
                price_change_percent = (price - previous_price) / previous_price * 100

            changes.append({
                "symbol": symbol,
                "change_percent": change_percent,
                "previous_oi": previous_oi,
                "current_oi": current_oi,
                "price": price,
                "previous_price": previous_price,
                "price_change_percent": price_change_percent,
                "current_oi_usdt": current_oi_usdt,
            })

            if index % 50 == 0:
                print(f"進度: {index}/{len(symbols)}")

            time.sleep(0.05)

        self.save_snapshot(current_snapshot)
        self.previous_snapshot = current_snapshot
        print(f"{now()} 本輪完成，有效 OI 變化數據 {len(changes)} 個。")
        return sorted(changes, key=lambda item: abs(item["change_percent"]), reverse=True)

    def print_top_changes(self, changes, limit=20):
        if not changes:
            print(f"{now()} 本輪沒有可輸出的 OI 變化數據。")
            return

        print(f"\n{now()} 本輪 OI 變化 Top {min(limit, len(changes))}:")
        print(f"{'排名':<4} {'交易對':<14} {'OI變化%':>9} {'價格':>12} {'價格變化%':>9} {'當前價值':>16}")
        print("-" * 74)

        telegram_lines = [
            f"{'#':<3} {'Symbol':<13} {'OI%':>8} {'Value':>8}",
            "-" * 38,
        ]

        for rank, item in enumerate(changes[:limit], 1):
            oi_usdt = item["current_oi_usdt"]
            oi_usdt_text = f"${oi_usdt:,.0f}" if oi_usdt is not None else "N/A"
            short_oi_usdt_text = format_short_usdt(oi_usdt)
            price_text = format_price(item["price"])
            price_change_text = format_percent(item["price_change_percent"])
            print(
                f"{rank:<4} "
                f"{item['symbol']:<14} "
                f"{item['change_percent']:>8.2f}% "
                f"{price_text:>12} "
                f"{price_change_text:>9} "
                f"{oi_usdt_text:>16}"
            )
            telegram_lines.append(
                f"{rank:<3} "
                f"{item['symbol'][:13]:<13} "
                f"{item['change_percent']:>7.2f}% "
                f"{short_oi_usdt_text:>8}"
            )
        print()

        message = (
            f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"<pre>{html_escape(chr(10).join(telegram_lines))}</pre>"
        )
        self.notifier.send(message, parse_mode="HTML")

    def print_alerts(self, changes):
        alerts = [item for item in changes if item["change_percent"] >= self.alert_percent]
        if not alerts:
            return

        for item in alerts:
            oi_usdt = item["current_oi_usdt"]
            oi_usdt_text = f"${oi_usdt:,.0f}" if oi_usdt is not None else "N/A"
            price_text = format_price(item["price"])
            price_change_text = format_percent(item["price_change_percent"])
            message = (
                f"🔥 異動提醒: {item['symbol']} 本輪持倉增長 {item['change_percent']:.2f}% "
                f"(當前價格: {price_text}, 價格變化: {price_change_text}, 當前價值: {oi_usdt_text})"
            )
            print(message)
            self.notifier.send(message)
        print()


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_short_usdt(value):
    if value is None:
        return "N/A"

    abs_value = abs(value)
    if abs_value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if abs_value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if abs_value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:.0f}"


def format_price(value):
    if value is None:
        return "N/A"
    return f"${value:,.6g}"


def format_percent(value):
    if value is None:
        return "N/A"

    prefix = "+" if value >= 0 else ""
    return f"{prefix}{value:.2f}%"


def html_escape(value):
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def sleep_until_next_run(interval_seconds, started_at):
    elapsed = time.time() - started_at
    sleep_seconds = max(0, interval_seconds - elapsed)
    next_run = datetime.fromtimestamp(time.time() + sleep_seconds).strftime("%Y-%m-%d %H:%M:%S")
    print(f"下一次掃描時間: {next_run}")
    time.sleep(sleep_seconds)


def run_forever(interval_minutes=60, alert_percent=10.0, telegram_bot_token=None, telegram_chat_id=None):
    if interval_minutes <= 0:
        raise ValueError("interval_minutes 必須大於 0")
    if alert_percent <= 0:
        raise ValueError("alert_percent 必須大於 0")

    notifier = TelegramNotifier(bot_token=telegram_bot_token, chat_id=telegram_chat_id)
    monitor = BinanceOIMonitor(alert_percent=alert_percent, notifier=notifier)
    interval_seconds = interval_minutes * 60

    print(f"{now()} BNOI 24 小時監控啟動，每 {interval_minutes} 分鐘掃描一次。")
    print(f"對比方式: 當前掃描結果 vs 上一輪掃描結果")
    print(f"提醒條件: 本輪 OI 增長 >= {alert_percent:.2f}%")
    print(f"Telegram 推送: {'已啟用' if notifier.enabled else '未啟用'}")
    print(f"快照文件: {monitor.snapshot_file}")
    print("第一輪掃描會建立基準，第二輪開始輸出變化。")

    while True:
        started_at = time.time()

        try:
            changes = monitor.collect_interval_changes()
            if changes:
                monitor.print_top_changes(changes, limit=20)
                monitor.print_alerts(changes)
            else:
                print(f"{now()} 本輪沒有拿到有效 OI 變化數據。")
        except KeyboardInterrupt:
            print("\n已停止 BNOI 監控。")
            break
        except Exception as e:
            print(f"{now()} 本輪監控失敗: {e}")

        try:
            sleep_until_next_run(interval_seconds, started_at)
        except KeyboardInterrupt:
            print("\n已停止 BNOI 監控。")
            break


def parse_args():
    load_env_file()

    parser = argparse.ArgumentParser(description="BNOI 24 小時 OI 監控器")
    parser.add_argument("--interval-minutes", type=int, default=30, help="掃描間隔，預設 60 分鐘")
    parser.add_argument("--alert-percent", type=float, default=5.0, help="OI 增長提醒閾值，預設 10%%")
    parser.add_argument("--telegram-bot-token", default=os.getenv("TELEGRAM_BOT_TOKEN"), help="Telegram Bot Token")
    parser.add_argument("--telegram-chat-id", default=os.getenv("TELEGRAM_CHAT_ID"), help="Telegram Chat ID")
    return parser.parse_args()


def main(interval_minutes=60, alert_percent=10.0, telegram_bot_token=None, telegram_chat_id=None):
    load_env_file()

    run_forever(
        interval_minutes=interval_minutes,
        alert_percent=alert_percent,
        telegram_bot_token=telegram_bot_token or os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=telegram_chat_id or os.getenv("TELEGRAM_CHAT_ID"),
    )


if __name__ == "__main__":
    args = parse_args()
    main(
        interval_minutes=args.interval_minutes,
        alert_percent=args.alert_percent,
        telegram_bot_token=args.telegram_bot_token,
        telegram_chat_id=args.telegram_chat_id,
    )
