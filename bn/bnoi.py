import requests
import time
import os
from datetime import datetime

class BinanceFutures:
    def __init__(self):
        self.base_url = "https://fapi.binance.com"
        self.data_url = f"{self.base_url}/futures/data/openInterestHist"
        self.info_url = f"{self.base_url}/fapi/v1/exchangeInfo"
        self.price_url = f"{self.base_url}/fapi/v1/ticker/price"

    def get_active_symbols(self):
        """獲取交易中的 USDT 永續合約"""
        try:
            resp = requests.get(self.info_url, timeout=10).json()
            symbols = [
                s['symbol'] for s in resp['symbols'] 
                if s['quoteAsset'] == 'USDT' and s['status'] == 'TRADING' and s['contractType'] == 'PERPETUAL'
            ]

            return symbols
        except Exception as e:
            print(f"❌ 獲取列表失敗: {e}")
            return []

    def get_symbol_price(self, symbol):
        """獲取單個幣種的當前價格"""
        try:
            resp = requests.get(self.price_url, params={'symbol': symbol}, timeout=5).json()
            return float(resp['price'])
        except:
            return 1.0 # 獲取失敗則默認為1，避免程序崩潰

    def get_oi_analysis(self, symbol):
        """抓取數據並折算為 USDT 價值"""
        params = {'symbol': symbol, 'period': '1h', 'limit': 170}
        try:
            # 1. 獲取持倉數量歷史
            resp = requests.get(self.data_url, params=params, timeout=5)
            data = resp.json()
            if not isinstance(data, list) or len(data) < 169:
                return None

            # 2. 獲取當前價格用來折算 USDT
            price = self.get_symbol_price(symbol)

            # 3. 計算持倉量 (數量)
            curr_oi_amount = float(data[-1]['sumOpenInterest'])
            oi_1d_amount = float(data[-25]['sumOpenInterest'])
            oi_7d_amount = float(data[-169]['sumOpenInterest'])

            # 4. 折算為 USDT 價值 (當前價值)
            curr_oi_usdt = curr_oi_amount * price

            return {
                'symbol': symbol,
                'curr_oi_usdt': curr_oi_usdt,
                'ch_1d': round((curr_oi_amount - oi_1d_amount) / oi_1d_amount * 100, 2),
                'ch_7d': round((curr_oi_amount - oi_7d_amount) / oi_7d_amount * 100, 2)
            }
        except:
            return None

def export_reports(results, folder="ticket"):
    if not os.path.exists(folder):
        os.makedirs(folder)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    configs = [
        {'key': 'ch_7d', 'name': '7日增幅', 'suffix': '7d'},
        {'key': 'ch_1d', 'name': '1日增幅', 'suffix': '1d'}
    ]

    for cfg in configs:
        sorted_data = sorted(results, key=lambda x: x[cfg['key']], reverse=True)
        file_path = f"{folder}/oi_rank_{cfg['suffix']}.txt"
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"幣安合約 OI 報告 (USDT價值) - 排序基準: {cfg['name']}\n")
            f.write(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*80 + "\n")
            # 格式化表頭
            f.write(f"{'排名':<3} {'交易對':<13} {'當前持倉價值(USDT)':<22} {'1日OI%':>7} {'7日OI%':>12}\n")
            f.write("-" * 80 + "\n")
            
            for idx, item in enumerate(sorted_data[:50], 1):
                # 對價值進行千分位格式化，方便閱讀
                oi_str = f"{item['curr_oi_usdt']:,.0f}"
                f.write(f"{idx:<4} {item['symbol']:<15} {oi_str:<22} {item['ch_1d']:>11}% {item['ch_7d']:>11}%\n")
            f.write("=" * 80 + "\n")
        
        print(f"📊 已導出 {cfg['name']} 報告: {file_path}")

def main():
    api = BinanceFutures()
    print(f"--- 幣安合約 OI 價值掃描器 (啟動時間: {datetime.now().strftime('%H:%M')}) ---")

    symbols = api.get_active_symbols()
    if not symbols: return
    print(f"🔍 掃描到 {len(symbols)} 個活躍合約，開始計算 USDT 持倉價值...")

    all_results = []
    for i, sym in enumerate(symbols):
        res = api.get_oi_analysis(sym)
        if res:
            all_results.append(res)
            if abs(res['ch_7d']) > 50:
                print(f"🔥 異動提醒: {sym} 7日持倉增長 {res['ch_7d']}% (當前價值: ${res['curr_oi_usdt']:,.0f})")

        if (i + 1) % 20 == 0:
            print(f"進度: {i + 1}/{len(symbols)}...")
        
        #time.sleep(0.15) # 增加了一次價格請求，稍微延長延遲保護 IP

    if all_results:
        print("\n--- 正在生成報告 ---")
        export_reports(all_results)
        print("\n✅ 任務完成！")

if __name__ == "__main__":
    main()