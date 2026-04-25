import requests
import os
try:
    from bn.base_asset_map import BASE_ASSET_MAP
except ImportError:
    from base_asset_map import BASE_ASSET_MAP



def save_pairs_to_file(pairs, folder, filename):
    """通用函式：將交易對列表存入檔案"""
    if not pairs:
        print(f"沒有找到 {filename} 的相關交易對，或發生錯誤。")
        return

    # 確保資料夾存在
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, filename)

    try:
        with open(filepath, 'w') as f:
            f.write('\n'.join(pairs) + '\n')
        print(f"成功將 {len(pairs)} 個交易對寫入至 {filepath}")
    except IOError as e:
        print(f"檔案寫入失敗: {e}")


def get_futures_pairs():
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    
    try:
        response = requests.get(url)
        response.raise_for_status() # 檢查 HTTP 狀態碼
        data = response.json()
    except Exception as e:
        print(f"請求失敗: {e}")
        return

    # 初始化容器
    tradfi_pairs = []
    futures_pairs = []

    # 優化：只遍歷一次 symbols 清單，並進行過濾
    for symbol_info in data.get('symbols', []):
        # 基本過濾條件
        if symbol_info.get('status') != "TRADING" or symbol_info.get('quoteAsset') != 'USDT':
            continue

        pair_symbol = BASE_ASSET_MAP.get(
            symbol_info.get('symbol'),
            symbol_info.get('symbol'),
        )
        
        symbol_name = f"Binance:{pair_symbol}.p"
        contract_type = symbol_info.get('contractType')



        if contract_type == 'TRADIFI_PERPETUAL':
            tradfi_pairs.append(symbol_name)
        elif contract_type == 'PERPETUAL':
            futures_pairs.append(symbol_name)

    # 執行儲存
    output_dir = 'ticket'
    save_pairs_to_file(tradfi_pairs, output_dir, 'binance_tradfi_pairs.txt')
    save_pairs_to_file(futures_pairs, output_dir, 'binance_futures_pairs.txt')


def main():
    get_futures_pairs()


if __name__ == "__main__":
    main()
