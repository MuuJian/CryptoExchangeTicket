import requests
import os

def save_to_file(data_list, folder, filename):
    """通用函式：自動建立資料夾並寫入檔案"""
    if not data_list:
        print(f"[-] 沒有找到交易對，或資料為空。")
        return

    # 自動建立資料夾 (避免路徑不存在報錯)
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, filename)

    try:
        with open(filepath, 'w') as f:
            # 使用 join 一次性寫入，效能較好
            f.write('\n'.join(data_list) + '\n')
        print(f"[+] 成功將 {len(data_list)} 個現貨交易對寫入至: {filepath}")
    except IOError as e:
        print(f"[!] 檔案寫入失敗: {e}")

def get_spot_pairs():
    """獲取幣安現貨 USDT 交易對"""
    url = "https://api.binance.com/api/v3/exchangeInfo"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"[!] 網路請求失敗: {e}")
        return

    # 過濾條件：報價貨幣為 USDT 且 狀態為 TRADING
    # 這裡直接在 List Comprehension 處理，簡潔有力
    usdt_pairs = [
        f"Binance:{symbol['symbol']}" 
        for symbol in data.get('symbols', []) 
        if symbol.get('quoteAsset') == 'USDT' and symbol.get('status') == 'TRADING'
    ]

    # 執行儲存
    save_to_file(usdt_pairs, 'ticket', 'binance_usdt_pairs.txt')

def main():
    get_spot_pairs()

if __name__ == "__main__":
    main()
