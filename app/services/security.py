"""Password hashing.

Passwords are never stored or compared directly. Each one is stretched with
PBKDF2-HMAC-SHA256 under a salt unique to that user, so two people choosing the
same password produce different stored values and a leaked database cannot be
reversed with a precomputed table.
"""
import hashlib
import secrets

ALGORITHM = "sha256"
ROUNDS = 600_000  # OWASP guidance for PBKDF2-HMAC-SHA256
SALT_BYTES = 16


def new_salt():
    return secrets.token_hex(SALT_BYTES)


def hash_password(password, salt=None):
    """Return (salt, hash) as hex strings."""
    salt = salt or new_salt()
    digest = hashlib.pbkdf2_hmac(
        ALGORITHM, password.encode("utf-8"), bytes.fromhex(salt), ROUNDS
    )
    return salt, digest.hex()


# compared in constant time so the comparison cannot be used to learn the
# stored value one character at a time
def verify_password(password, salt, expected_hash):
    _, candidate = hash_password(password, salt)
    return secrets.compare_digest(candidate, expected_hash)
