import tempfile
import unittest
from pathlib import Path

from exchange_ticket.bn.tradfi import (
    LEGACY_MISSPELLED_FILENAME,
    TRADFI_FILENAME,
    is_spot_tradfi,
    update_tradfi_watchlist,
)


class TradFiWatchlistTests(unittest.TestCase):
    def test_recognizes_known_spot_equity_tokens(self):
        self.assertTrue(is_spot_tradfi("NVDAB"))
        self.assertFalse(is_spot_tradfi("BTC"))

    def test_updates_one_market_without_losing_the_other(self):
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            update_tradfi_watchlist(
                ["Binance:XAUUSDT.p"],
                market="futures",
                folder=output_dir,
            )
            update_tradfi_watchlist(
                ["Binance:NVDABUSDT"],
                market="spot",
                folder=output_dir,
            )
            self.assertEqual(
                (output_dir / TRADFI_FILENAME).read_text(encoding="utf-8").splitlines(),
                ["Binance:NVDABUSDT", "Binance:XAUUSDT.p"],
            )

    def test_migrates_legacy_misspelled_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            legacy = output_dir / LEGACY_MISSPELLED_FILENAME
            legacy.write_text("Binance:XAUUSDT.p\n", encoding="utf-8")
            update_tradfi_watchlist(
                ["Binance:NVDABUSDT"],
                market="spot",
                folder=output_dir,
            )
            self.assertFalse(legacy.exists())
            self.assertTrue((output_dir / TRADFI_FILENAME).exists())


if __name__ == "__main__":
    unittest.main()
