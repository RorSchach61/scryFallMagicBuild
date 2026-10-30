import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.models.card import Card
from app.services import security
from app.services.deck_repository import SqliteDeckRepository
from app.services.user_repository import (
    DuplicateUserError, SqliteUserRepository, UserNotFoundError)
from app.services.user_validation import ValidationError

PASSWORD = "hunter2hunter2"


class UserRepositoryTest(unittest.TestCase):

    def setUp(self):
        # the real work factor is asserted in test_security; lowering it here
        # keeps this suite quick without changing the code path under test
        patcher = mock.patch.object(security, "ROUNDS", 1_000)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.repo = SqliteUserRepository(Path(self.dir.name) / "magic.db")
        self.addCleanup(self.repo.close)

    def create(self, username="willr", display_name="Will R", password=PASSWORD):
        return self.repo.create(username, display_name, password, password)


class CreateTest(UserRepositoryTest):

    def test_returns_the_stored_user(self):
        user = self.create()
        self.assertEqual(user.username, "willr")
        self.assertEqual(user.display_name, "Will R")
        self.assertIsNotNone(user.user_id)

    def test_strips_surrounding_whitespace(self):
        user = self.create(username="  willr  ", display_name="  Will R  ")
        self.assertEqual(user.username, "willr")
        self.assertEqual(user.display_name, "Will R")

    def test_blank_display_name_is_stored_as_none(self):
        user = self.create(display_name="")
        self.assertIsNone(user.display_name)
        self.assertEqual(user.label(), "willr")

    def test_rejects_a_duplicate_username(self):
        self.create()
        with self.assertRaises(DuplicateUserError):
            self.create()

    def test_duplicate_check_ignores_case(self):
        self.create(username="willr")
        with self.assertRaises(DuplicateUserError):
            self.create(username="WILLR")

    def test_duplicate_error_is_a_validation_error(self):
        # so the interface can catch one type for every rejection
        self.create()
        with self.assertRaises(ValidationError):
            self.create()

    def test_rejects_invalid_input(self):
        with self.assertRaises(ValidationError):
            self.create(username="ab")

    def test_rejected_user_is_not_stored(self):
        with self.assertRaises(ValidationError):
            self.create(username="ab")
        self.assertEqual(self.repo.all_users(), [])

    def test_rejects_mismatched_confirmation(self):
        with self.assertRaises(ValidationError):
            self.repo.create("willr", "", PASSWORD, "somethingelse")


class UpdateTest(UserRepositoryTest):

    def test_returns_the_changed_user(self):
        user = self.create()
        updated = self.repo.update(user.user_id, "dana", "Dana")
        self.assertEqual(updated.user_id, user.user_id)
        self.assertEqual(updated.username, "dana")
        self.assertEqual(updated.display_name, "Dana")

    def test_change_is_stored(self):
        user = self.create()
        self.repo.update(user.user_id, "dana", "Dana")
        self.assertIsNone(self.repo.find("willr"))
        self.assertEqual(self.repo.find("dana").user_id, user.user_id)

    def test_strips_surrounding_whitespace(self):
        user = self.create()
        updated = self.repo.update(user.user_id, "  dana  ", "  Dana  ")
        self.assertEqual(updated.username, "dana")
        self.assertEqual(updated.display_name, "Dana")

    def test_blank_display_name_is_stored_as_none(self):
        user = self.create()
        self.assertIsNone(self.repo.update(user.user_id, "willr", "").display_name)

    def test_rejects_a_taken_username(self):
        self.create(username="willr")
        dana = self.create(username="dana")
        with self.assertRaises(DuplicateUserError):
            self.repo.update(dana.user_id, "willr", "")

    def test_taken_check_ignores_case(self):
        self.create(username="willr")
        dana = self.create(username="dana")
        with self.assertRaises(DuplicateUserError):
            self.repo.update(dana.user_id, "WILLR", "")

    def test_refused_rename_changes_nothing(self):
        self.create(username="willr")
        dana = self.create(username="dana", display_name="Dana")
        with self.assertRaises(DuplicateUserError):
            self.repo.update(dana.user_id, "willr", "Someone Else")
        self.assertEqual(self.repo.find("dana").display_name, "Dana")

    def test_user_can_change_the_case_of_their_own_name(self):
        # the unique index compares against other rows, not the row being changed
        user = self.create(username="willr")
        self.assertEqual(self.repo.update(user.user_id, "WillR", "").username, "WillR")

    def test_rejects_invalid_input(self):
        user = self.create()
        with self.assertRaises(ValidationError):
            self.repo.update(user.user_id, "ab", "")

    def test_rejected_input_changes_nothing(self):
        user = self.create()
        with self.assertRaises(ValidationError):
            self.repo.update(user.user_id, "ab", "")
        self.assertIsNotNone(self.repo.find("willr"))

    def test_unknown_id_raises(self):
        with self.assertRaises(UserNotFoundError):
            self.repo.update(999, "ghost", "")

    def test_password_survives_a_rename(self):
        user = self.create()
        self.repo.update(user.user_id, "dana", "")
        self.assertIsNotNone(self.repo.authenticate("dana", PASSWORD))


class DeleteTest(UserRepositoryTest):

    def setUp(self):
        super().setUp()
        self.decks = SqliteDeckRepository(Path(self.dir.name) / "magic.db")
        self.addCleanup(self.decks.close)

    def count(self, table):
        return self.decks.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def test_removes_the_user(self):
        user = self.create()
        self.repo.delete(user.user_id)
        self.assertIsNone(self.repo.find("willr"))

    def test_deleted_user_cannot_sign_in(self):
        user = self.create()
        self.repo.delete(user.user_id)
        self.assertIsNone(self.repo.authenticate("willr", PASSWORD))

    def test_leaves_other_users_alone(self):
        willr = self.create(username="willr")
        self.create(username="dana")
        self.repo.delete(willr.user_id)
        self.assertEqual([u.username for u in self.repo.all_users()], ["dana"])

    def test_unknown_id_raises(self):
        with self.assertRaises(UserNotFoundError):
            self.repo.delete(999)

    def test_not_found_is_a_validation_error(self):
        # so the interface shows it the same way as every other rejection
        with self.assertRaises(ValidationError):
            self.repo.delete(999)

    def test_cascade_removes_their_decks_and_cards(self):
        user = self.create()
        deck = self.decks.create(user.user_id, "Elves")
        forest = Card.create_from_json({"name": "Forest", "oracle_id": "id-forest"})
        self.decks.add_card(user.user_id, deck.deck_id, forest)

        self.repo.delete(user.user_id)

        self.assertEqual(self.count("decks"), 0)
        self.assertEqual(self.count("deck_cards"), 0)

    def test_cascade_leaves_other_users_decks_alone(self):
        willr = self.create(username="willr")
        dana = self.create(username="dana")
        self.decks.create(willr.user_id, "Elves")
        self.decks.create(dana.user_id, "Goblins")

        self.repo.delete(willr.user_id)

        self.assertEqual([d.name for d in self.decks.decks_for(dana.user_id)], ["Goblins"])


class StorageTest(UserRepositoryTest):

    def test_password_is_not_stored_in_plaintext(self):
        self.create()
        row = self.repo.conn.execute("SELECT * FROM users").fetchone()
        self.assertNotIn(PASSWORD, str(dict(row)))

    def test_two_users_sharing_a_password_get_different_salts(self):
        self.create(username="willr")
        self.create(username="dana")
        rows = self.repo.conn.execute("SELECT password_salt, password_hash FROM users").fetchall()
        self.assertNotEqual(rows[0]["password_salt"], rows[1]["password_salt"])
        self.assertNotEqual(rows[0]["password_hash"], rows[1]["password_hash"])

    def test_renaming_to_a_taken_username_is_refused(self):
        # the unique index guards renames too, so an update method must turn
        # this into a DuplicateUserError the way create does
        self.create(username="willr")
        self.create(username="dana")
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.conn.execute(
                "UPDATE users SET username = ? WHERE username = ?", ("WILLR", "dana"))


class FindTest(UserRepositoryTest):

    def test_finds_an_existing_user(self):
        self.create()
        self.assertEqual(self.repo.find("willr").username, "willr")

    def test_find_ignores_case(self):
        self.create()
        self.assertIsNotNone(self.repo.find("WiLlR"))

    def test_find_ignores_whitespace(self):
        self.create()
        self.assertIsNotNone(self.repo.find("  willr  "))

    def test_missing_user_is_none(self):
        self.assertIsNone(self.repo.find("ghost"))


class AllUsersTest(UserRepositoryTest):

    def test_empty_to_start(self):
        self.assertEqual(self.repo.all_users(), [])

    def test_lists_in_creation_order(self):
        self.create(username="willr")
        self.create(username="dana")
        self.assertEqual([u.username for u in self.repo.all_users()], ["willr", "dana"])


class AuthenticateTest(UserRepositoryTest):

    def test_correct_password_returns_the_user(self):
        self.create()
        self.assertEqual(self.repo.authenticate("willr", PASSWORD).username, "willr")

    def test_wrong_password_returns_none(self):
        self.create()
        self.assertIsNone(self.repo.authenticate("willr", "wrongpassword"))

    def test_unknown_user_returns_none(self):
        self.assertIsNone(self.repo.authenticate("ghost", PASSWORD))

    def test_empty_password_returns_none(self):
        self.create()
        self.assertIsNone(self.repo.authenticate("willr", ""))

    def test_none_password_returns_none(self):
        self.create()
        self.assertIsNone(self.repo.authenticate("willr", None))

    def test_username_case_does_not_matter(self):
        self.create()
        self.assertIsNotNone(self.repo.authenticate("WILLR", PASSWORD))


class PersistenceTest(unittest.TestCase):

    def test_users_survive_reopening(self):
        patcher = mock.patch.object(security, "ROUNDS", 1_000)
        patcher.start()
        self.addCleanup(patcher.stop)

        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "magic.db"

        first = SqliteUserRepository(path)
        first.create("willr", "Will R", PASSWORD, PASSWORD)
        first.close()

        second = SqliteUserRepository(path)
        self.addCleanup(second.close)
        self.assertIsNotNone(second.authenticate("willr", PASSWORD))


if __name__ == "__main__":
    unittest.main()
