import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.services import security
from app.services.user_repository import DuplicateUserError, SqliteUserRepository
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
