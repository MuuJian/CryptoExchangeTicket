import requests

def get_futures_pairs():
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        futures_pairs = [f"Binance:{symbol['symbol']}.p" for symbol in data['symbols'] 
                              if symbol.get('status') == "TRADING" and symbol.get('contractType') == 'PERPETUAL']
        return futures_pairs

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

futures_pairs = get_futures_pairs()
if futures_pairs:
    with open('binance_futures_pairs.txt', 'w') as file:
        for pair in futures_pairs:
            file.write(pair + '\n')
    print("futures pairs have been written to binance_futures.txt")
else:
    print("No futures pairs found or an error occurred.")