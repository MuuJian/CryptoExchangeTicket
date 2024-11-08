from pybit.unified_trading import HTTP

# 创建 HTTP 会话
Session = HTTP(testnet=False)

try:
    # 获取线性期货的交易对信息
    Ticket = Session.get_instruments_info(category="linear")['result']['list']
    
    # 过滤出以 USDT 为报价货币的交易对
    FuturePairs = [f"Bybit:{Symbols['symbol']}.p" for Symbols in Ticket if Symbols['quoteCoin'] == 'USDT']

    # 检查是否找到了交易对并写入文件
    if FuturePairs:
        with open('ticket/bybit_future_pairs.txt', 'w') as File:
            for Pair in FuturePairs:
                File.write(Pair + '\n')
        print("Futures pairs have been written to bybit_future_pairs.txt")
    else:
        print("No futures pairs found.")
        
except Exception as E:
    print(f"An error occurred: {E}")