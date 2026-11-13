import tempfile
import unittest
from pathlib import Path

from app.repositories.user_repository import SqliteUserRepository
from app.services.local_user import LOCAL_USERNAME, local_user


class LocalUserTest(unittest.TestCase):

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.users = SqliteUserRepository(Path(folder.name) / "magic.db")

    def test_a_fresh_install_gets_a_local_user(self):
        user = local_user(self.users)
        self.assertEqual(user.username, LOCAL_USERNAME)

    def test_the_same_user_comes_back_on_the_next_start(self):
        first = local_user(self.users)
        second = local_user(self.users)
        self.assertEqual(first.user_id, second.user_id)
        self.assertEqual(len(self.users.all_users()), 1)

    def test_an_existing_account_is_reused_so_its_decks_stay(self):
        old = self.users.create("will")
        self.users.create("other")
        self.assertEqual(local_user(self.users).user_id, old.user_id)


if __name__ == "__main__":
    unittest.main()
