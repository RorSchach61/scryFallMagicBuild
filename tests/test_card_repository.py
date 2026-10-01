import unittest

from app.models.card import Card
from app.services.card_repository import InMemoryCardRepository

NAMES = [
    "Forest", "Forestfolk", "Forest Bear", "Deep Forest Hermit",
    "Misty Rainforest", "Lightning Bolt", "Mountain",
]


def repository():
    return InMemoryCardRepository(
        Card.create_from_json({"name": name}) for name in NAMES
    )


class SearchTest(unittest.TestCase):

    def setUp(self):
        self.repo = repository()

    def test_returns_every_match(self):
        found = [card.name for card in self.repo.search("forest")]
        self.assertEqual(len(found), 5)
        self.assertNotIn("Mountain", found)

    def test_orders_closest_match_first(self):
        found = [card.name for card in self.repo.search("forest")]
        self.assertEqual(found[0], "Forest")
        self.assertEqual(found[-1], "Misty Rainforest")

    def test_is_case_insensitive(self):
        self.assertEqual(len(self.repo.search("FOREST")), 5)

    def test_ignores_surrounding_whitespace(self):
        self.assertEqual(len(self.repo.search("  forest  ")), 5)

    def test_multi_word_term_matches(self):
        found = [card.name for card in self.repo.search("lightning bolt")]
        self.assertEqual(found, ["Lightning Bolt"])

    def test_limit_caps_results(self):
        self.assertEqual(len(self.repo.search("forest", limit=2)), 2)

    def test_limit_keeps_the_best_matches(self):
        found = [card.name for card in self.repo.search("forest", limit=2)]
        self.assertEqual(found, ["Forest", "Forestfolk"])

    def test_empty_term_returns_nothing(self):
        self.assertEqual(self.repo.search(""), [])

    def test_whitespace_term_returns_nothing(self):
        self.assertEqual(self.repo.search("   "), [])

    def test_unknown_term_returns_nothing(self):
        self.assertEqual(self.repo.search("zzzznotacard"), [])

    def test_returns_card_objects(self):
        self.assertIsInstance(self.repo.search("forest")[0], Card)


class CountTest(unittest.TestCase):

    def test_counts_every_card(self):
        self.assertEqual(repository().count(), len(NAMES))

    def test_empty_repository(self):
        self.assertEqual(InMemoryCardRepository([]).count(), 0)


if __name__ == "__main__":
    unittest.main()
