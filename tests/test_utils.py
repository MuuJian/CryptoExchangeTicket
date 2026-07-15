import tempfile
import unittest
from pathlib import Path

from exchange_ticket.utils import (
    optional_float,
    optional_int,
    save_chunked_lines,
    save_lines,
    unique_lines,
)


class UtilsTests(unittest.TestCase):
    def test_unique_lines_preserves_order_and_removes_blanks(self):
        self.assertEqual(unique_lines([" BTC ", "", "ETH", "BTC"]), ["BTC", "ETH"])

    def test_optional_numbers_reject_invalid_values(self):
        self.assertEqual(optional_float("1.5", multiplier=100), 150)
        self.assertIsNone(optional_float("bad"))
        self.assertEqual(optional_int("12"), 12)
        self.assertIsNone(optional_int(None))

    def test_save_lines_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            output = save_lines(["BTC", "ETH"], "list.txt", Path(directory) / "nested")
            self.assertEqual(output.read_text(encoding="utf-8"), "BTC\nETH\n")

    def test_chunked_export_removes_stale_parts(self):
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            save_chunked_lines(["A", "B", "C", "D", "E"], "pairs.txt", output_dir, 2)
            paths = save_chunked_lines(["A", "B", "C"], "pairs.txt", output_dir, 2)

            self.assertEqual([path.name for path in paths], ["pairs.txt", "pairs_2.txt"])
            self.assertFalse((output_dir / "pairs_3.txt").exists())

    def test_chunk_size_must_be_positive(self):
        with self.assertRaisesRegex(ValueError, "greater than 0"):
            save_chunked_lines(["BTC"], "pairs.txt", chunk_size=0)

    def test_empty_export_removes_previous_files(self):
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            save_chunked_lines(["A", "B", "C"], "pairs.txt", output_dir, 2)
            save_chunked_lines([], "pairs.txt", output_dir, 2)
            self.assertEqual(list(output_dir.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
