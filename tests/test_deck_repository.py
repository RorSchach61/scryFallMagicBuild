import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.models.card import Card
from app.services import security
from app.services.deck_repository import (
    DeckError, DeckNotFoundError, DuplicateDeckError, SqliteDeckRepository,
)
from app.services.user_repository import SqliteUserRepository

PASSWORD = "hunter2hunter2"


def card(name, oracle_id=None):
    return Card.create_from_json({"name": name, "oracle_id": oracle_id or f"id-{name}"})


class DeckRepositoryTest(unittest.TestCase):

    def setUp(self):
        patcher = mock.patch.object(security, "ROUNDS", 1_000)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name) / "magic.db"

        # decks reference users, so the users table has to exist first
        self.users = SqliteUserRepository(self.path)
        self.addCleanup(self.users.close)
        self.will = self.users.create("willr", "Will R", PASSWORD, PASSWORD).user_id
        self.dana = self.users.create("dana", "Dana", PASSWORD, PASSWORD).user_id

        self.repo = SqliteDeckRepository(self.path)
        self.addCleanup(self.repo.close)


class CreateTest(DeckRepositoryTest):

    def test_returns_the_new_deck(self):
        deck = self.repo.create(self.will, "Zombies")
        self.assertIsNotNone(deck.deck_id)
        self.assertEqual(deck.name, "Zombies")
        self.assertEqual(deck.user_id, self.will)

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(self.repo.create(self.will, "  Zombies  ").name, "Zombies")

    def test_rejects_a_blank_name(self):
        with self.assertRaises(DeckError):
            self.repo.create(self.will, "   ")

    def test_rejects_a_long_name(self):
        with self.assertRaises(DeckError):
            self.repo.create(self.will, "a" * 65)

    def test_rejects_a_duplicate_name_ignoring_case(self):
        self.repo.create(self.will, "Zombies")
        with self.assertRaises(DuplicateDeckError):
            self.repo.create(self.will, "ZOMBIES")

    def test_two_users_can_share_a_deck_name(self):
        self.repo.create(self.will, "Zombies")
        self.assertIsNotNone(self.repo.create(self.dana, "Zombies"))

    def test_errors_are_value_errors(self):
        # so the interface can catch one type for every rejection
        with self.assertRaises(ValueError):
            self.repo.create(self.will, "")


class DecksForTest(DeckRepositoryTest):

    def test_empty_to_start(self):
        self.assertEqual(self.repo.decks_for(self.will), [])

    def test_lists_only_the_users_own_decks(self):
        self.repo.create(self.will, "Zombies")
        self.repo.create(self.dana, "Elves")
        self.assertEqual([d.name for d in self.repo.decks_for(self.will)], ["Zombies"])

    def test_alphabetical(self):
        for name in ("zombies", "Burn", "elves"):
            self.repo.create(self.will, name)
        self.assertEqual([d.name for d in self.repo.decks_for(self.will)],
                         ["Burn", "elves", "zombies"])

    def test_card_count_adds_up_copies(self):
        deck = self.repo.create(self.will, "Zombies")
        self.repo.add_card(self.will, deck.deck_id, card("Forest"), quantity=4)
        self.repo.add_card(self.will, deck.deck_id, card("Gravecrawler"))
        self.assertEqual(self.repo.decks_for(self.will)[0].card_count, 5)

    def test_empty_deck_counts_zero(self):
        self.repo.create(self.will, "Zombies")
        self.assertEqual(self.repo.decks_for(self.will)[0].card_count, 0)


class CardsTest(DeckRepositoryTest):

    def setUp(self):
        super().setUp()
        self.deck = self.repo.create(self.will, "Zombies").deck_id

    def entries(self):
        return [(e.name, e.quantity) for e in self.repo.cards_in(self.will, self.deck)]

    def test_new_deck_is_empty(self):
        self.assertEqual(self.entries(), [])

    def test_add_card(self):
        self.repo.add_card(self.will, self.deck, card("Gravecrawler"))
        self.assertEqual(self.entries(), [("Gravecrawler", 1)])

    def test_adding_again_stacks_copies(self):
        self.repo.add_card(self.will, self.deck, card("Gravecrawler"))
        self.repo.add_card(self.will, self.deck, card("Gravecrawler"), quantity=2)
        self.assertEqual(self.entries(), [("Gravecrawler", 3)])

    def test_entries_are_alphabetical(self):
        self.repo.add_card(self.will, self.deck, card("Zombie Master"))
        self.repo.add_card(self.will, self.deck, card("Diregraf Ghoul"))
        self.assertEqual([name for name, _ in self.entries()], ["Diregraf Ghoul", "Zombie Master"])

    def test_rejects_a_card_without_an_id(self):
        no_id = Card.create_from_json({"name": "Mystery"})
        with self.assertRaises(DeckError):
            self.repo.add_card(self.will, self.deck, no_id)

    def test_rejects_zero_quantity(self):
        with self.assertRaises(DeckError):
            self.repo.add_card(self.will, self.deck, card("Forest"), quantity=0)

    def test_remove_counts_down(self):
        self.repo.add_card(self.will, self.deck, card("Forest"), quantity=3)
        self.repo.remove_card(self.will, self.deck, "id-Forest")
        self.assertEqual(self.entries(), [("Forest", 2)])

    def test_removing_the_last_copy_drops_the_card(self):
        self.repo.add_card(self.will, self.deck, card("Forest"))
        self.repo.remove_card(self.will, self.deck, "id-Forest")
        self.assertEqual(self.entries(), [])

    def test_removing_more_than_held_drops_the_card(self):
        self.repo.add_card(self.will, self.deck, card("Forest"), quantity=2)
        self.repo.remove_card(self.will, self.deck, "id-Forest", quantity=5)
        self.assertEqual(self.entries(), [])

    def test_removing_a_card_not_in_the_deck_is_harmless(self):
        self.repo.remove_card(self.will, self.deck, "id-Nothing")
        self.assertEqual(self.entries(), [])


class DeleteTest(DeckRepositoryTest):

    def test_removes_the_deck(self):
        deck = self.repo.create(self.will, "Zombies")
        self.repo.delete(self.will, deck.deck_id)
        self.assertEqual(self.repo.decks_for(self.will), [])

    def test_removes_the_decks_cards_too(self):
        deck = self.repo.create(self.will, "Zombies")
        self.repo.add_card(self.will, deck.deck_id, card("Forest"))
        self.repo.delete(self.will, deck.deck_id)
        count = self.repo.conn.execute("SELECT COUNT(*) FROM deck_cards").fetchone()[0]
        self.assertEqual(count, 0)

    def test_missing_deck_raises(self):
        with self.assertRaises(DeckNotFoundError):
            self.repo.delete(self.will, 999)


# the important guarantee: nothing one user does can reach another user's deck
class OwnershipTest(DeckRepositoryTest):

    def setUp(self):
        super().setUp()
        self.wills_deck = self.repo.create(self.will, "Zombies").deck_id
        self.repo.add_card(self.will, self.wills_deck, card("Forest"))

    def test_cannot_read_another_users_deck(self):
        with self.assertRaises(DeckNotFoundError):
            self.repo.cards_in(self.dana, self.wills_deck)

    def test_cannot_add_to_another_users_deck(self):
        with self.assertRaises(DeckNotFoundError):
            self.repo.add_card(self.dana, self.wills_deck, card("Island"))

    def test_cannot_remove_from_another_users_deck(self):
        with self.assertRaises(DeckNotFoundError):
            self.repo.remove_card(self.dana, self.wills_deck, "id-Forest")
        self.assertEqual(len(self.repo.cards_in(self.will, self.wills_deck)), 1)

    def test_cannot_delete_another_users_deck(self):
        with self.assertRaises(DeckNotFoundError):
            self.repo.delete(self.dana, self.wills_deck)
        self.assertEqual(len(self.repo.decks_for(self.will)), 1)


class PersistenceTest(DeckRepositoryTest):

    def test_decks_survive_reopening(self):
        deck = self.repo.create(self.will, "Zombies")
        self.repo.add_card(self.will, deck.deck_id, card("Forest"), quantity=2)
        self.repo.close()

        reopened = SqliteDeckRepository(self.path)
        self.addCleanup(reopened.close)
        entries = reopened.cards_in(self.will, deck.deck_id)
        self.assertEqual([(e.name, e.quantity) for e in entries], [("Forest", 2)])

    def test_deleting_a_user_deletes_their_decks(self):
        self.repo.create(self.will, "Burn")
        # no delete method on the user repo yet, so delete through its connection
        self.users.conn.execute("DELETE FROM users WHERE user_id = ?", (self.will,))
        self.users.conn.commit()
        self.assertEqual(self.repo.decks_for(self.will), [])


if __name__ == "__main__":
    unittest.main()
