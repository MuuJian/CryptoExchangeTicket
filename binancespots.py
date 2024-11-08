import requests

def GetSpotPairs():
    Url = "https://api.binance.com/api/v3/exchangeInfo"
    try:
        Response = requests.get(Url)
        Response.raise_for_status()  # 检查请求是否成功
        Data = Response.json()

        # 打印数据以检查格式
        # print(json.dumps(Data, indent=2))

        # 过滤出以 USDT 为报价货币且状态为 TRADING 的交易对
        UsdtPairs = [f"Binance:{Symbol['symbol']}" for Symbol in Data['symbols'] 
                     if Symbol.get('quoteAsset') == 'USDT' and Symbol.get('status') == 'TRADING']
        return UsdtPairs

    except requests.exceptions.RequestException as E:
        print(f"Request failed: {E}")
    except Exception as E:
        print(f"An error occurred: {E}")

UsdtPairs = GetSpotPairs()
if UsdtPairs:
    with open('ticket/binance_usdt_pairs.txt', 'w') as File:
        for Pair in UsdtPairs:
            File.write(Pair + '\n')
    print("USDT pairs have been written to binance_usdt_pairs.txt")
else:
    print("No USDT pairs found or an error occurred.")