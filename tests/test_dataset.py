import gzip
import json
import tempfile
import unittest
from pathlib import Path

from app.services.dataset import DatasetMissingError, read_cards

CARDS = [
    {"name": "Forest", "type_line": "Basic Land — Forest"},
    {"name": "Æther Vial", "type_line": "Artifact"},
]


class ReadCardsTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name) / "oracle_cards.jsonl.gz"

    def write(self, lines):
        with gzip.open(self.path, "wt", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def test_yields_each_card(self):
        self.write([json.dumps(card) for card in CARDS])
        self.assertEqual(list(read_cards(self.path)), CARDS)

    def test_skips_blank_lines(self):
        self.write([json.dumps(CARDS[0]), "", "   ", json.dumps(CARDS[1])])
        self.assertEqual(len(list(read_cards(self.path))), 2)

    def test_reads_non_ascii_names(self):
        self.write([json.dumps(card) for card in CARDS])
        self.assertEqual(list(read_cards(self.path))[1]["name"], "Æther Vial")

    def test_is_lazy(self):
        # nothing should be read until the generator is consumed
        self.write([json.dumps(card) for card in CARDS])
        cards = read_cards(self.path)
        self.assertEqual(next(iter(cards))["name"], "Forest")

    def test_missing_file_raises(self):
        missing = Path(self.dir.name) / "absent.jsonl.gz"
        with self.assertRaises(DatasetMissingError):
            list(read_cards(missing))

    def test_missing_file_error_is_a_file_not_found(self):
        missing = Path(self.dir.name) / "absent.jsonl.gz"
        with self.assertRaises(FileNotFoundError):
            list(read_cards(missing))


if __name__ == "__main__":
    unittest.main()
