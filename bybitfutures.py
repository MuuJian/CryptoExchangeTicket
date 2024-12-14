from pybit.unified_trading import HTTP

def GetFuturesPairs():
    Session = HTTP(testnet=False)

    Ticket = Session.get_instruments_info(category="linear")['result']['list']
    FuturePairs = [f"Bybit:{Symbols['symbol']}.p" for Symbols in Ticket
                    if Symbols['quoteCoin'] == 'USDT']
    return FuturePairs


FuturePairs = GetFuturesPairs()
if FuturePairs:
    with open('ticket/bybit_future_pairs.txt', 'w') as File:
        for Pair in FuturePairs:
                File.write(Pair + '\n')
        print("Futures pairs have been written to bybit_future_pairs.txt")
else:
    print("No futures pairs found.")
