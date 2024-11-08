from pybit.unified_trading import HTTP

Session = HTTP(testnet=False)
Ticket = Session.get_instruments_info(category="spot")['result']['list']
UsdtPairs = [f"Bybit:{Symbols['symbol']}" for Symbols in Ticket if Symbols['quoteCoin'] == 'USDT']

if UsdtPairs:
    with open('ticket/bybit_spot_pairs.txt', 'w') as File:
        for Pair in UsdtPairs:
            File.write(Pair + '\n')
    print("Spot pairs have been written to bybit_spot_pairs.txt")
else:
    print("No spot pairs found or an error occurred.")