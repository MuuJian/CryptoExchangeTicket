import requests

def GetSpotPairs():
    Url = "https://api.binance.com/api/v3/exchangeInfo"

    Response = requests.get(Url)
    Data = Response.json()

    UsdtPairs = [f"Binance:{Symbol['symbol']}" for Symbol in Data['symbols'] 
                if Symbol.get('quoteAsset') == 'USDT' and Symbol.get('status') == 'TRADING']
    return UsdtPairs


UsdtPairs = GetSpotPairs()
if UsdtPairs:
    with open('ticket/binance_usdt_pairs.txt', 'w') as File:
        for Pair in UsdtPairs:
            File.write(Pair + '\n')
    print("USDT pairs have been written to binance_usdt_pairs.txt")
else:
    print("No USDT pairs found or an error occurred.")