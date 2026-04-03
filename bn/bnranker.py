import requests
import time
import os
from datetime import datetime


# 官方API基础域名
BASE_URL = "https://api.binance.com"
FUTURES_URL = "https://fapi.binance.com"


def get_symbols(is_futures=False):

    """获取过滤后的交易对"""
    url = f"{FUTURES_URL if is_futures else BASE_URL}/{'fapi/v1/exchangeInfo' if is_futures else 'api/v3/exchangeInfo'}"
    try:
        resp = requests.get(url, timeout=10).json()
        symbols = []
        for s in resp['symbols']:
            if (s['quoteAsset'] == 'USDT' and s['status'] == 'TRADING'
                and s['contractType'] == 'PERPETUAL'):
                    symbols.append(s['symbol'])
        return symbols
    except Exception as e:
        print(f"获取列表失败: {e}")
        return []

def get_change(symbol, is_futures=False):

    """获取特定币种涨幅"""
    url = f"{FUTURES_URL if is_futures else BASE_URL}/{'fapi/v1/klines' if is_futures else 'api/v3/klines'}"
    # 每次获取31根日线，即过去一个月
    params = {'symbol': symbol, 'interval': '1d', 'limit': 31}

    try:
        data = requests.get(url, params=params, timeout=5).json()
        if not isinstance(data, list) or len(data) < 31: return None
        
        # 币安K线: 索引4是收盘价 (即当天8点价格)
        curr_p = float(data[-1][4])    # 最新价
        p_1d = float(data[-2][4])      # 1天前 8:00
        p_1w = float(data[-8][4])      # 7天前 8:00
        p_1m = float(data[-31][4])     # 30天前 8:00
        
        return {
            'symbol': symbol,
            'price': curr_p,
            '1d': round((curr_p - p_1d) / p_1d * 100, 2),
            '1w': round((curr_p - p_1w) / p_1w * 100, 2),
            '1m': round((curr_p - p_1m) / p_1m * 100, 2)
        }
    except:
        return None


def export_to_txt(data, sort_key, is_futures):
    """将数据排序并导出为TXT文件"""
    key_names = {'1d': '日涨幅', '1w': '周涨幅', '1m': '月涨幅'}
    
    # 排序
    sorted_res = sorted(data, key=lambda x: x[sort_key], reverse=True)
    
    # 创建 ticket 文件夹
    folder_name = "ticket"
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
    
    # 生成文件名
    file_name = f"{folder_name}/bn_{'fut' if is_futures else 'spot'}_{sort_key}.txt"
    
    # 写入TXT文件 (取前50名)
    with open(file_name, mode='w', encoding='utf-8') as f:
        f.write(f"币安行情报告 - 排序基准: {key_names[sort_key]}\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*75 + "\n")
        f.write(f"{'排名':<3} {'交易对':<12} {'当前价格':<8} {'1日%':>10} {'1周%':>10} {'1月%':>10}\n")
        f.write("-" * 75 + "\n")
        
        for idx, item in enumerate(sorted_res[:50], 1):
            line = f"{idx:<4} {item['symbol']:<14} {item['price']:<12.4f} {item['1d']:>9.2f}% {item['1w']:>9.2f}% {item['1m']:>9.2f}%\n"
            f.write(line)
        f.write("=" * 75 + "\n")

    print(f"✅ 文件已成功导出至: {file_name}")


def main():
    print("--- 币安行情自动扫描器 ---")
    
    # 自动定义任务清单：(是否合约, 市场名称)
    tasks = [(True, "合约")]
    #tasks = [(False, "现货"), (True, "合约")]
    
    for is_f, market_name in tasks:
        print(f"\n正在扫描 {market_name} 市场...")
        
        # 1. 获取币种列表
        all_symbols = get_symbols(is_futures=is_f)
        if not all_symbols: continue
        
        print(f"发现 {len(all_symbols)} 个交易对，正在计算涨幅...")
        
        # 2. 获取数据 (这步最耗时)
        results = []
        for i, sym in enumerate(all_symbols):
            res = get_change(sym, is_futures=is_f)
            if res:
                results.append(res)
            if (i + 1) % 50 == 0:
                print(f"进度: {i + 1}/{len(all_symbols)}...")
            #time.sleep(0.01) # 略微提速

        # 3. 自动导出周和月
        print(f"正在导出 {market_name} 的 周 和 月 排名...")
        export_to_txt(results, '1w', is_f)
        #export_to_txt(results, '1m', is_f)
        
    print("\n任务全部完成。")

if __name__ == "__main__":
    main()