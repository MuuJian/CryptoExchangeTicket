import unittest

from exchange_ticket.bitget.bitget import build_spot_pairs as build_bitget_spot_pairs
from exchange_ticket.bn.bnfutures import build_futures_pairs
from exchange_ticket.bn.bnspots import build_spot_pairs as build_binance_spot_pairs
from exchange_ticket.bybit.bybitfutures import build_futures_pairs as build_bybit_futures_pairs
from exchange_ticket.bybit.bybitspot import build_spot_pairs as build_bybit_spot_pairs
from exchange_ticket.okx.okx import build_spot_pairs as build_okx_spot_pairs


class WatchlistBuilderTests(unittest.TestCase):
    def test_binance_spot_filters_and_maps_symbols(self):
        payload = {
            "symbols": [
                {"symbol": "BTCUSDT", "quoteAsset": "USDT", "status": "TRADING"},
                {"symbol": "币安人生USDT", "quoteAsset": "USDT", "status": "TRADING"},
                {"symbol": "ETHBTC", "quoteAsset": "BTC", "status": "TRADING"},
            ]
        }
        self.assertEqual(
            build_binance_spot_pairs(payload),
            (["Binance:BTCUSDT", "Binance:BIANRENSHENGUSDT"], []),
        )

    def test_binance_futures_splits_contract_types(self):
        payload = {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "quoteAsset": "USDT",
                    "status": "TRADING",
                    "contractType": "PERPETUAL",
                },
                {
                    "symbol": "XAUUSDT",
                    "quoteAsset": "USDT",
                    "status": "TRADING",
                    "contractType": "TRADIFI_PERPETUAL",
                },
            ]
        }
        self.assertEqual(
            build_futures_pairs(payload),
            (["Binance:XAUUSDT.p"], ["Binance:BTCUSDT.p"]),
        )

    def test_other_exchange_builders_filter_inactive_markets(self):
        active = {"symbol": "BTCUSDT", "quoteCoin": "USDT", "status": "Trading"}
        inactive = {"symbol": "ETHUSDT", "quoteCoin": "USDT", "status": "Closed"}
        self.assertEqual(build_bybit_spot_pairs([active, inactive]), ["Bybit:BTCUSDT"])
        self.assertEqual(build_bybit_futures_pairs([active, inactive]), ["Bybit:BTCUSDT.p"])

        self.assertEqual(
            build_bitget_spot_pairs(
                {"data": [{"symbol": "BTCUSDT", "quoteCoin": "USDT", "status": "online"}]}
            ),
            ["Bitget:BTCUSDT"],
        )
        self.assertEqual(
            build_okx_spot_pairs(
                [{"baseCcy": "BTC", "quoteCcy": "USDT", "state": "live"}]
            ),
            ["okx:BTCUSDT"],
        )


if __name__ == "__main__":
    unittest.main()
