import unittest

from app.services import user_validation as validation


class UsernameTest(unittest.TestCase):

    def test_accepts_a_normal_name(self):
        self.assertIsNone(validation.check_username("willr"))

    def test_accepts_underscore_and_hyphen(self):
        self.assertIsNone(validation.check_username("will_r-61"))

    def test_rejects_empty(self):
        self.assertIn("required", validation.check_username(""))

    def test_rejects_whitespace_only(self):
        self.assertIn("required", validation.check_username("   "))

    def test_rejects_none(self):
        self.assertIn("required", validation.check_username(None))

    def test_rejects_too_short(self):
        self.assertIn("at least", validation.check_username("ab"))

    def test_rejects_too_long(self):
        self.assertIn("at most", validation.check_username("a" * 33))

    def test_rejects_spaces_inside(self):
        self.assertIn("may only contain", validation.check_username("will r"))

    def test_rejects_punctuation(self):
        self.assertIn("may only contain", validation.check_username("will!"))

    def test_ignores_surrounding_whitespace(self):
        self.assertIsNone(validation.check_username("  willr  "))


class DisplayNameTest(unittest.TestCase):

    def test_optional(self):
        self.assertIsNone(validation.check_display_name(""))
        self.assertIsNone(validation.check_display_name(None))

    def test_rejects_too_long(self):
        self.assertIn("at most", validation.check_display_name("a" * 65))

    def test_allows_spaces_and_punctuation(self):
        self.assertIsNone(validation.check_display_name("Will R. (he/they)"))


class PasswordTest(unittest.TestCase):

    def test_accepts_long_enough(self):
        self.assertIsNone(validation.check_password("hunter2hunter2"))

    def test_rejects_empty(self):
        self.assertIn("required", validation.check_password(""))

    def test_rejects_too_short(self):
        self.assertIn("at least", validation.check_password("short"))

    def test_rejects_mismatch(self):
        self.assertIn("do not match", validation.check_password("longenough1", "longenough2"))

    def test_accepts_matching_confirmation(self):
        self.assertIsNone(validation.check_password("longenough1", "longenough1"))


class CheckNewUserTest(unittest.TestCase):

    def test_accepts_valid_input(self):
        self.assertIsNone(
            validation.check_new_user("willr", "Will R", "hunter2hunter2", "hunter2hunter2")
        )

    def test_reports_username_before_password(self):
        problem = validation.check_new_user("ab", "", "short", "other")
        self.assertIn("at least 3", problem)

    def test_reports_password_when_username_is_fine(self):
        problem = validation.check_new_user("willr", "", "short", "short")
        self.assertIn("at least 8", problem)


if __name__ == "__main__":
    unittest.main()
