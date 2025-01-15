import requests

def GetSpotPairs():
    Url = "https://www.okx.com/api/v5/public/instruments"
    Params = {
        "instType": "SPOT"  # 可选值：SPOT、MARGIN、SWAP、FUTURES、OPTION
    }

    Response = requests.get(Url, params=Params)
    Data = Response.json()['data']
    
    UsdtPairs = [f"okx:{Symbols['baseCcy']}{Symbols['quoteCcy']}" for Symbols in Data 
               if Symbols['quoteCcy'] == 'USDT']

    if UsdtPairs:
        with open('ticket/okx_spot_pairs.txt', 'w') as File:
            for Pair in UsdtPairs:
                File.write(Pair + '\n')
        print("Spot pairs have been written to okx_spot_pairs.txt")
    else:
        print("No spot pairs found or an error occurred.")


def main():
    GetSpotPairs()

if __name__ == "__main__":
    main()
