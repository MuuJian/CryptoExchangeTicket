import requests

def GetFuturesPairs():
    Url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    try:
        Response = requests.get(Url)
        Response.raise_for_status()
        Data = Response.json()

        FuturesPairs = [f"Binance:{Symbol['symbol']}.p" for Symbol in Data['symbols'] 
                        if Symbol.get('status') == "TRADING" and Symbol.get('contractType') == 'PERPETUAL' and Symbol.get('quoteAsset') == 'USDT']
        return FuturesPairs

    except requests.exceptions.RequestException as E:
        print(f"Request failed: {E}")
    except Exception as E:
        print(f"An error occurred: {E}")

FuturesPairs = GetFuturesPairs()
if FuturesPairs:
    with open('ticket/binance_futures_pairs.txt', 'w') as File:
        for Pair in FuturesPairs:
            File.write(Pair + '\n')
    print("Futures pairs have been written to binance_futures_pairs.txt")
else:
    print("No futures pairs found or an error occurred.")