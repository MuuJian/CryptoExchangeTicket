from pybit.unified_trading import HTTP

def GetFuturesPairs():
    Session = HTTP(testnet=False)

    Ticket = Session.get_instruments_info(category="linear")['result']['list']
    
    FuturePairs = [f"Bybit:{Symbols['symbol']}.p" for Symbols in Ticket
                    if Symbols['quoteCoin'] == 'USDT']
    
    if FuturePairs:
        with open('ticket/bybit_future_pairs.txt', 'w') as File:
            File.write('\n'.join(FuturePairs) + '\n')
            
        print("Futures pairs have been written to bybit_future_pairs.txt")
    else:
        print("No futures pairs found.")

def main():
    GetFuturesPairs()

if __name__ == "__main__":
    main()
