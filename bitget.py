import requests

def GetSpotPairs():
    Url = "https://api.bitget.com/api/spot/v1/public/products"  # Bitget 现货交易对列表 API

    Response = requests.get(Url)
    Data = Response.json()

    Instruments = [f"Bitget:{Symbols['symbolName']}" for Symbols in Data['data']
                    if Symbols.get('quoteCoin') == 'USDT']
    
    return Instruments


UsdtPairs = GetSpotPairs()
if UsdtPairs:
    with open('ticket/bitget_spot_pairs.txt', 'w') as File:
        for Pair in UsdtPairs:
            File.write(Pair + '\n')
    print("Spot pairs have been written to bitget_spot_pairs.txt")
else:
    print("No spot pairs found or an error occurred.")
