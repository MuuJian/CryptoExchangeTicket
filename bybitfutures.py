import requests

def get_linear_futures_symbols():
    url = "https://api.bybit.com/v2/public/symbols"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        # 过滤线性期货交易对
        linear_futures = [f"Bybit:{symbol['name']}.p" for symbol in data['result'] 
                          if symbol['quote_currency'] in ['USDT']]
        return linear_futures

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

linear_futures = get_linear_futures_symbols()
if linear_futures:
    with open('bybit_futures_pairs.txt', 'w') as file:
        for pair in linear_futures:
            file.write(pair + '\n')
    print("futures pairs have been written to bybit_futures_pairs.txt")
else:
    print("No futures pairs found or an error occurred.")