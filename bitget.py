from pybit.unified_trading import HTTP

def GetSpotPairs():
    Session = HTTP(testnet=False)

    Ticket = Session.get_instruments_info(category="spot")['result']['list']
    
    Instruments = [f"Bybit:{Symbols['symbol']}" for Symbols in Ticket
                if Symbols.get('quoteCoin') == 'USDT' and Symbols.get('status') == 'Trading']
                    
    return Instruments


UsdtPairs = GetSpotPairs()
if UsdtPairs:
    with open('ticket/bitget_spot_pairs.txt', 'w') as File:
        for Pair in UsdtPairs:
            File.write(Pair + '\n')
    print("Spot pairs have been written to bitget_spot_pairs.txt")
else:
    print("No spot pairs found or an error occurred.")
