def main():
    from exchange_ticket.bn import bnfutures, bnspots

    #bitget.main()
    #bybitfutures.main()
    #bybitspot.main()
    #okx.main()
    #bnoi.main()

    bnfutures.main()
    bnspots.main()
    #binance_oi_monitor.main(interval_minutes=30, alert_percent=5.0)


if __name__ == "__main__":
    main()
