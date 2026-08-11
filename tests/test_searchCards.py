import unittest

from app.services.searchCards import cardSearch


class NormalizeTest(unittest.TestCase):

    def test_strips_and_lowers(self):
        self.assertEqual(cardSearch.normalize("  Forest  "), "forest")

    def test_handles_none(self):
        self.assertEqual(cardSearch.normalize(None), "")


class MatchesTest(unittest.TestCase):

    def test_substring_matches_anywhere(self):
        self.assertTrue(cardSearch.matches("Misty Rainforest", "forest"))

    def test_is_case_insensitive(self):
        self.assertTrue(cardSearch.matches("Forest", "FOREST"))

    def test_rejects_absent_term(self):
        self.assertFalse(cardSearch.matches("Forest", "mountain"))

    def test_partial_word_matches(self):
        # the old implementation split on whitespace, so this returned False
        self.assertTrue(cardSearch.matches("Lightning Bolt", "lightning bolt"))


class RankTest(unittest.TestCase):

    def test_exact_name(self):
        self.assertEqual(cardSearch.rank("Forest", "forest"), cardSearch.EXACT)

    def test_name_starting_with_term(self):
        self.assertEqual(cardSearch.rank("Forestfolk", "forest"), cardSearch.PREFIX)

    def test_later_word_starting_with_term(self):
        self.assertEqual(
            cardSearch.rank("Deep Forest Hermit", "forest"), cardSearch.WORD_START
        )

    def test_term_buried_inside_a_word(self):
        self.assertEqual(
            cardSearch.rank("Misty Rainforest", "forest"), cardSearch.CONTAINS
        )

    def test_face_separator_does_not_hide_a_word(self):
        self.assertEqual(
            cardSearch.rank("Emeritus of Conflict // Lightning Bolt", "lightning"),
            cardSearch.WORD_START,
        )


class SortKeyTest(unittest.TestCase):

    def test_orders_by_closeness_then_length(self):
        names = ["Misty Rainforest", "Deep Forest Hermit", "Forestfolk", "Forest"]
        ordered = sorted(names, key=lambda name: cardSearch.sortKey(name, "forest"))
        self.assertEqual(
            ordered,
            ["Forest", "Forestfolk", "Deep Forest Hermit", "Misty Rainforest"],
        )

    def test_equal_rank_falls_back_to_shorter_name(self):
        names = ["Forest Bear", "Forestfolk"]
        ordered = sorted(names, key=lambda name: cardSearch.sortKey(name, "forest"))
        self.assertEqual(ordered, ["Forestfolk", "Forest Bear"])


if __name__ == "__main__":
    unittest.main()
