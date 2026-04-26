import bn.bnfutures as bnfutures
import bn.bnspots as bnspots
import bn.bnranker as bnranker
import bn.binance_oi_monitor as binance_oi_monitor
import bn.bnoi as bnoi
import bitget.bitget as bitget
import bybit.bybitfutures as bybitfutures
import bybit.bybitspot as bybitspot
import okx.okx as okx

def main():
    bnfutures.main()
    bnspots.main()
    binance_oi_monitor.main(interval_minutes=30, alert_percent=5.0)
    #bnoi.main()
    #bnranker.main()

    #bitget.main()
    #bybitfutures.main()
    #bybitspot.main()
    #okx.main()


if __name__ == "__main__":
    main()
