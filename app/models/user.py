"""User record.

Holds data only. Hashing lives in services/security.py and the rules about what
makes a username acceptable live in services/user_validation.py, so this stays
a plain description of a stored row.
"""
import time


class User:
    def __init__(self, username, display_name, password_salt, password_hash,
                 created_at=None, user_id=None):
        self.user_id = user_id
        self.username = username
        self.display_name = display_name
        self.password_salt = password_salt
        self.password_hash = password_hash
        self.created_at = created_at if created_at is not None else time.time()

    # what the interface shows, falling back to the login name
    def label(self):
        return self.display_name or self.username

    def __repr__(self):
        return f"User({self.username!r})"
