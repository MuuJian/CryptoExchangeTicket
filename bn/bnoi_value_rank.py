import argparse
import os
import time
from datetime import datetime

import requests


class BinanceOIValueRanker:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://fapi.binance.com"
        self.info_url = f"{self.base_url}/fapi/v1/exchangeInfo"
        self.price_url = f"{self.base_url}/fapi/v1/ticker/price"
        self.oi_url = f"{self.base_url}/fapi/v1/openInterest"

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

    def get_prices(self):
        try:
            resp = self.session.get(self.price_url, timeout=10)
            resp.raise_for_status()
            return {
                item["symbol"]: float(item["price"])
                for item in resp.json()
                if "symbol" in item and "price" in item
            }
        except Exception as e:
            print(f"獲取價格失敗: {e}")
            return {}

    def get_open_interest(self, symbol):
        try:
            resp = self.session.get(self.oi_url, params={"symbol": symbol}, timeout=8)
            resp.raise_for_status()
            return float(resp.json()["openInterest"])
        except Exception as e:
            print(f"{symbol} OI 獲取失敗: {e}")
            return None

    def build_rank(self):
        symbols = self.get_active_symbols()
        prices = self.get_prices()
        results = []

        print(f"掃描 {len(symbols)} 個 USDT 永續合約...")
        for index, symbol in enumerate(symbols, 1):
            oi_amount = self.get_open_interest(symbol)
            price = prices.get(symbol)
            if oi_amount is None or price is None:
                continue

            results.append({
                "symbol": symbol,
                "price": price,
                "oi_amount": oi_amount,
                "oi_value": oi_amount * price,
            })

            if index % 50 == 0:
                print(f"進度: {index}/{len(symbols)}")

            time.sleep(0.03)

        return sorted(results, key=lambda item: item["oi_value"], reverse=True)


def export_rank(items, target_symbol, limit=50, folder="ticket"):
    os.makedirs(folder, exist_ok=True)
    file_path = os.path.join(folder, "binance_oi_value_rank.txt")
    target_symbol = target_symbol.upper()
    target_rank = None
    target_item = None

    for index, item in enumerate(items, 1):
        if item["symbol"] == target_symbol:
            target_rank = index
            target_item = item
            break

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("Binance USDT 永續合約 OI 價值排名\n")
        f.write(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 76 + "\n")
        f.write(f"{'排名':<4} {'交易對':<14} {'價格':>12} {'OI數量':>18} {'OI價值':>18}\n")
        f.write("-" * 76 + "\n")

        for index, item in enumerate(items[:limit], 1):
            f.write(
                f"{index:<4} "
                f"{item['symbol']:<14} "
                f"${item['price']:>11,.6g} "
                f"{item['oi_amount']:>18,.4f} "
                f"${item['oi_value']:>17,.0f}\n"
            )

        if target_item:
            f.write("=" * 76 + "\n")
            f.write(
                f"{target_symbol} 排名: {target_rank}/{len(items)}, "
                f"價格: ${target_item['price']:,.6g}, "
                f"OI價值: ${target_item['oi_value']:,.0f}\n"
            )

    print(f"已輸出 OI 價值排名: {file_path}")
    if target_item:
        print(
            f"{target_symbol} 排名: {target_rank}/{len(items)} | "
            f"價格: ${target_item['price']:,.6g} | "
            f"OI價值: ${target_item['oi_value']:,.0f}"
        )
    else:
        print(f"沒有在 USDT 永續合約裡找到 {target_symbol}")


def parse_args():
    parser = argparse.ArgumentParser(description="Binance OI value ranker")
    parser.add_argument("--symbol", default="CCUSDT", help="要查排名的交易對，預設 SAGAUSDT")
    parser.add_argument("--limit", type=int, default=50, help="輸出排名前 N 個，預設 50")
    return parser.parse_args()


def main():
    args = parse_args()
    ranker = BinanceOIValueRanker()
    items = ranker.build_rank()
    if not items:
        print("沒有拿到有效 OI 數據。")
        return

    export_rank(items, target_symbol=args.symbol, limit=args.limit)


if __name__ == "__main__":
    main()
