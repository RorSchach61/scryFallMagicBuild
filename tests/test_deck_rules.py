import unittest

from app.models.card import Card
from app.models.deck import DeckEntry
from app.services.deck_rules import illegal_entries

CARDS = {
    card.oracle_id: card for card in (
        Card.create_from_json({"name": "Lightning Bolt", "oracle_id": "bolt",
                               "legalities": {"modern": "legal"}}),
        Card.create_from_json({"name": "Mana Crypt", "oracle_id": "crypt",
                               "legalities": {"modern": "not_legal",
                                              "commander": "banned",
                                              "vintage": "restricted"}}),
    )
}


def entry(oracle_id):
    return DeckEntry(oracle_id, oracle_id, 1)


def check(format_key, *oracle_ids):
    found = illegal_entries(format_key, [entry(i) for i in oracle_ids], CARDS.get)
    return [(e.oracle_id, status) for e, status in found]


class IllegalEntriesTest(unittest.TestCase):

    def test_legal_cards_pass(self):
        self.assertEqual(check("modern", "bolt"), [])

    def test_reports_not_legal(self):
        self.assertEqual(check("modern", "bolt", "crypt"), [("crypt", "not_legal")])

    def test_reports_banned(self):
        self.assertEqual(check("commander", "crypt"), [("crypt", "banned")])

    def test_restricted_passes(self):
        self.assertEqual(check("vintage", "crypt"), [])

    def test_format_missing_from_card_data_is_not_legal(self):
        self.assertEqual(check("pauper", "bolt"), [("bolt", "not_legal")])

    def test_card_missing_from_dataset_is_unknown(self):
        self.assertEqual(check("modern", "gone"), [("gone", "unknown")])

    def test_no_format_checks_nothing(self):
        self.assertEqual(check(None, "crypt", "gone"), [])

    def test_empty_deck_has_no_problems(self):
        self.assertEqual(check("modern"), [])


if __name__ == "__main__":
    unittest.main()
