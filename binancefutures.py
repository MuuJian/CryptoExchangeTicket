import requests

def GetFuturesPairs():
    Url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    
    Response = requests.get(Url)
    Data = Response.json()

    FuturesPairs = [f"Binance:{Symbols['symbol']}.p" for Symbols in Data['symbols'] 
                    if Symbols.get('status') == "TRADING" and Symbols.get('contractType') == 'PERPETUAL' and Symbols.get('quoteAsset') == 'USDT']
    
    if FuturesPairs:
        with open('ticket/binance_futures_pairs.txt', 'w') as File:
            for Pair in FuturesPairs:
                File.write(Pair + '\n')
        print("Futures pairs have been written to binance_futures_pairs.txt")
    else:
        print("No futures pairs found or an error occurred.")


def main():
    GetFuturesPairs()

if __name__ == "__main__":
    main()
