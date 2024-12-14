import requests

def GetSpotPairs():
    Url = "https://api.binance.com/api/v3/exchangeInfo"

    Response = requests.get(Url)
    Data = Response.json()

    UsdtPairs = [f"Binance:{Symbols['symbol']}" for Symbols in Data['symbols'] 
                if Symbols.get('quoteAsset') == 'USDT' and Symbols.get('status') == 'TRADING']
    return UsdtPairs


UsdtPairs = GetSpotPairs()
if UsdtPairs:
    with open('ticket/binance_usdt_pairs.txt', 'w') as File:
        for Pair in UsdtPairs:
            File.write(Pair + '\n')
    print("USDT pairs have been written to binance_usdt_pairs.txt")
else:
    print("No USDT pairs found or an error occurred.")