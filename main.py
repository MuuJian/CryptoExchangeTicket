import requests

url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
headers = {"X-CMC_PRO_API_KEY": "1c02030fcd9e4fb7b8a9ca8ecc7fba70"}
params = {"symbol": "BTC,ETH,SOL", "convert": "USD"}

response = requests.get(url, headers=headers, params=params)
data = response.json()

for symbol, info in data["data"].items():
    market_cap = info["quote"]["USD"]["market_cap"]
    print(f"{symbol} 市值: ${market_cap:,.0f}")


