from bn import binance_oi_monitor, bnfutures, bnspots
from bn import bnoi
from bitget import bitget
from bybit import bybitfutures, bybitspot
from okx import okx

def main():
    #bitget.main()
    #bybitfutures.main()
    #bybitspot.main()
    #okx.main()
    #bnoi.main()

    bnfutures.main()
    bnspots.main()
    binance_oi_monitor.main(interval_minutes=30, alert_percent=5.0)


if __name__ == "__main__":
    main()
