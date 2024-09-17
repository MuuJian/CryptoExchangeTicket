import requests

def get_spot_pairs():
    url = "https://api.binance.com/api/v3/exchangeInfo"
    try:
        response = requests.get(url)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        
        # 打印数据以检查格式
        # print(json.dumps(data, indent=2))

        # 过滤出以 USDT 为报价货币且状态为 TRADING 的交易对
        usdt_pairs = [f"Binance:{symbol['symbol']}" for symbol in data['symbols'] 
                      if symbol.get('quoteAsset') == 'USDT' and symbol.get('status') == 'TRADING']
        return usdt_pairs

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

usdt_pairs = get_spot_pairs()
if usdt_pairs:
    with open('binance_usdt_pairs.txt', 'w') as file:
        for pair in usdt_pairs:
            file.write(pair + '\n')
    print("USDT pairs have been written to usdt_pairs.txt")
else:
    print("No USDT pairs found or an error occurred.")
    