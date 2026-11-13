import tempfile
import threading
import unittest
from pathlib import Path

from app.db.connection import connect
from app.repositories.user_repository import SqliteUserRepository


class UserRepositoryTest(unittest.TestCase):

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "magic.db"
        self.repo = SqliteUserRepository(self.path)

    def test_create_returns_the_stored_user(self):
        user = self.repo.create("local")
        self.assertEqual(user.username, "local")
        self.assertIsNotNone(user.user_id)

    def test_empty_to_start(self):
        self.assertEqual(self.repo.all_users(), [])

    def test_lists_in_creation_order(self):
        self.repo.create("willr")
        self.repo.create("dana")
        self.assertEqual([u.username for u in self.repo.all_users()], ["willr", "dana"])

    def test_users_survive_reopening(self):
        self.repo.create("local")
        self.assertEqual([u.username for u in SqliteUserRepository(self.path).all_users()],
                         ["local"])

    def test_reads_a_database_made_while_the_app_had_sign_in(self):
        with connect(self.path) as conn:
            conn.execute(
                """INSERT INTO users (username, display_name, password_salt,
                                      password_hash, created_at)
                   VALUES ('willr', 'Will R', 'salt', 'hash', 0)"""
            )
        [user] = SqliteUserRepository(self.path).all_users()
        self.assertEqual(user.username, "willr")

    def test_works_from_another_thread(self):
        self.repo.create("local")
        found = []
        thread = threading.Thread(target=lambda: found.extend(self.repo.all_users()))
        thread.start()
        thread.join()
        self.assertEqual([u.username for u in found], ["local"])


if __name__ == "__main__":
    unittest.main()
