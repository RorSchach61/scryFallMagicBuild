import unittest

from app.services import security


class HashPasswordTest(unittest.TestCase):

    def test_roundtrip_verifies(self):
        salt, digest = security.hash_password("hunter2hunter2")
        self.assertTrue(security.verify_password("hunter2hunter2", salt, digest))

    def test_wrong_password_fails(self):
        salt, digest = security.hash_password("hunter2hunter2")
        self.assertFalse(security.verify_password("hunter3hunter3", salt, digest))

    def test_same_password_gets_a_different_salt_each_time(self):
        salt_a, digest_a = security.hash_password("hunter2hunter2")
        salt_b, digest_b = security.hash_password("hunter2hunter2")
        self.assertNotEqual(salt_a, salt_b)
        self.assertNotEqual(digest_a, digest_b)

    def test_supplied_salt_is_reused(self):
        salt, digest = security.hash_password("hunter2hunter2")
        same_salt, same_digest = security.hash_password("hunter2hunter2", salt)
        self.assertEqual(salt, same_salt)
        self.assertEqual(digest, same_digest)

    def test_digest_is_not_the_password(self):
        _salt, digest = security.hash_password("hunter2hunter2")
        self.assertNotIn("hunter2hunter2", digest)

    def test_handles_non_ascii(self):
        salt, digest = security.hash_password("pässwörd–ü")
        self.assertTrue(security.verify_password("pässwörd–ü", salt, digest))


class SaltTest(unittest.TestCase):

    def test_is_hex_of_expected_length(self):
        salt = security.new_salt()
        self.assertEqual(len(salt), security.SALT_BYTES * 2)
        bytes.fromhex(salt)  # raises if not valid hex

    def test_salts_differ(self):
        self.assertNotEqual(security.new_salt(), security.new_salt())


class WorkFactorTest(unittest.TestCase):

    # guards against someone lowering the cost for convenience and leaving it
    def test_rounds_meet_owasp_guidance(self):
        self.assertGreaterEqual(security.ROUNDS, 600_000)

    def test_uses_sha256(self):
        self.assertEqual(security.ALGORITHM, "sha256")


if __name__ == "__main__":
    unittest.main()
