import json
import tempfile
import unittest
from pathlib import Path

from realtime_oi_dashboard.server import OIPoller


class OIPollerTests(unittest.TestCase):
    def test_restores_baseline_without_exposing_saved_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot_file = Path(directory) / "latest.json"
            snapshot_file.write_text(
                json.dumps(
                    {
                        "saved_at": "2026-01-01T00:00:00+08:00",
                        "snapshot": {"BTCUSDT": {"oi": 2, "price": 100}},
                        "rows": [
                            {
                                "symbol": "BTCUSDT",
                                "currentOi": 2,
                                "currentOiValue": 200,
                                "absChangePercent": 3,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            poller = OIPoller(snapshot_file=snapshot_file)
            state = poller.get_state()

            self.assertTrue(state["baseline"])
            self.assertEqual(state["rows"], [])
            self.assertIsNone(state["saved_at"])
            self.assertEqual(poller.snapshot["BTCUSDT"]["oi"], 2)

    def test_prunes_delisted_symbols(self):
        with tempfile.TemporaryDirectory() as directory:
            poller = OIPoller(snapshot_file=Path(directory) / "missing.json")
            poller.symbols = ["BTCUSDT"]
            poller.snapshot = {"BTCUSDT": {}, "OLDUSDT": {}}
            poller.rows_by_symbol = {"BTCUSDT": {}, "OLDUSDT": {}}
            poller.oi_24h_cache = {"OLDUSDT": {}}

            poller.prune_inactive_symbols()

            self.assertEqual(set(poller.snapshot), {"BTCUSDT"})
            self.assertEqual(set(poller.rows_by_symbol), {"BTCUSDT"})
            self.assertEqual(poller.oi_24h_cache, {})

    def test_build_oi_change(self):
        poller = OIPoller(snapshot_file=Path(tempfile.gettempdir()) / "missing-oi-test.json")
        self.assertEqual(
            poller.build_oi_change(120, 100, 2, "oi24h"),
            {
                "oi24hChangeAmount": 20,
                "oi24hChangePercent": 20,
                "oi24hChangeValue": 40,
            },
        )

    def test_snapshot_writes_are_throttled_and_can_be_forced(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot_file = Path(directory) / "latest.json"
            poller = OIPoller(snapshot_file=snapshot_file, snapshot_save_interval=60)
            poller.snapshot = {"BTCUSDT": {"oi": 1, "price": 100}}

            self.assertTrue(poller.save_state())
            poller.snapshot["BTCUSDT"]["oi"] = 2
            self.assertFalse(poller.save_state())
            self.assertEqual(json.loads(snapshot_file.read_text())["snapshot"]["BTCUSDT"]["oi"], 1)

            self.assertTrue(poller.save_state(force=True))
            saved_payload = json.loads(snapshot_file.read_text())
            self.assertEqual(saved_payload["snapshot"]["BTCUSDT"]["oi"], 2)
            self.assertNotIn("rows", saved_payload)


if __name__ == "__main__":
    unittest.main()
