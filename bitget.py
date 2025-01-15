import requests

def GetSpotPairs():
    Url = "https://api.bitget.com/api/spot/v1/public/products"

    Response = requests.get(Url)
    Data = Response.json()

    UsdtPairs = [f"Bitget:{Symbols['symbolName']}" for Symbols in Data['data'] 
                if Symbols.get('quoteCoin') == 'USDT' and Symbols.get('status') == 'online']

    if UsdtPairs:
        with open('ticket/bitget_spot_pairs.txt', 'w') as File:
            for Pair in UsdtPairs:
                File.write(Pair + '\n')
        print("Spot pairs have been written to bitget_spot_pairs.txt")
    else:
        print("No spot pairs found or an error occurred.")


def main():
    GetSpotPairs()

if __name__ == "__main__":
    main()
