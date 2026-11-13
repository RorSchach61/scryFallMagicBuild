"""User record.

The app is single-user, so a user is only the owner that decks hang off.
"""
import time


class User:
    def __init__(self, username, created_at=None, user_id=None):
        self.user_id = user_id
        self.username = username
        self.created_at = created_at if created_at is not None else time.time()

    def __repr__(self):
        return f"User({self.username!r})"
