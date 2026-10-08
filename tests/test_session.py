import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.services import security
from app.services.session import Session
from app.services.user_repository import SqliteUserRepository

PASSWORD = "hunter2hunter2"


class SessionTest(unittest.TestCase):

    def setUp(self):
        patcher = mock.patch.object(security, "ROUNDS", 1_000)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.users = SqliteUserRepository(Path(self.dir.name) / "magic.db")
        self.addCleanup(self.users.close)
        self.users.create("willr", "Will R", PASSWORD, PASSWORD)
        self.session = Session(self.users)


class StartsSignedOutTest(SessionTest):

    def test_not_authenticated(self):
        self.assertFalse(self.session.is_authenticated())

    def test_user_is_none(self):
        self.assertIsNone(self.session.user)

    def test_label_is_none(self):
        self.assertIsNone(self.session.label())


class LoginTest(SessionTest):

    def test_correct_credentials_sign_in(self):
        self.assertIsNotNone(self.session.login("willr", PASSWORD))
        self.assertTrue(self.session.is_authenticated())
        self.assertEqual(self.session.user.username, "willr")

    def test_label_uses_display_name(self):
        self.session.login("willr", PASSWORD)
        self.assertEqual(self.session.label(), "Will R")

    def test_username_case_does_not_matter(self):
        self.assertIsNotNone(self.session.login("WILLR", PASSWORD))

    def test_wrong_password_is_refused(self):
        self.assertIsNone(self.session.login("willr", "wrongpassword"))
        self.assertFalse(self.session.is_authenticated())

    def test_unknown_user_is_refused(self):
        self.assertIsNone(self.session.login("ghost", PASSWORD))
        self.assertFalse(self.session.is_authenticated())

    def test_empty_password_is_refused(self):
        self.assertIsNone(self.session.login("willr", ""))
        self.assertFalse(self.session.is_authenticated())

    # a mistyped password while already signed in must not sign the user out
    def test_failed_attempt_leaves_an_existing_session_intact(self):
        self.session.login("willr", PASSWORD)
        self.assertIsNone(self.session.login("willr", "wrongpassword"))
        self.assertTrue(self.session.is_authenticated())
        self.assertEqual(self.session.user.username, "willr")

    def test_signing_in_as_someone_else_replaces_the_user(self):
        self.users.create("dana", "Dana", PASSWORD, PASSWORD)
        self.session.login("willr", PASSWORD)
        self.session.login("dana", PASSWORD)
        self.assertEqual(self.session.user.username, "dana")


class LogoutTest(SessionTest):

    def test_clears_the_user(self):
        self.session.login("willr", PASSWORD)
        self.session.logout()
        self.assertFalse(self.session.is_authenticated())
        self.assertIsNone(self.session.user)

    def test_is_safe_when_already_signed_out(self):
        self.session.logout()
        self.assertFalse(self.session.is_authenticated())

    def test_can_sign_in_again_afterwards(self):
        self.session.login("willr", PASSWORD)
        self.session.logout()
        self.assertIsNotNone(self.session.login("willr", PASSWORD))


if __name__ == "__main__":
    unittest.main()
