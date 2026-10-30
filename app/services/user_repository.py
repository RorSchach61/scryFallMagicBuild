"""User storage, behind an interface.

Mirrors the card side: callers depend on UserRepository, and the SQLite backing
can be swapped without touching the interface above it.
"""
import sqlite3
import time
from abc import ABC, abstractmethod
from app.config import USER_DB_PATH
from app.models.user import User
from app.services import security
from app.services.user_validation import (
    ValidationError, check_display_name, check_new_user, check_username)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id       INTEGER PRIMARY KEY,
    username      TEXT NOT NULL,
    display_name  TEXT,
    password_salt TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    REAL NOT NULL
);
-- usernames compare case insensitively so Will and will cannot both exist
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username COLLATE NOCASE);
"""

class DuplicateUserError(ValidationError):
    """Raised when a username is already taken."""

# lookups answer None for a missing user; changes raise this instead, since
# changing a user that does not exist means the caller has a stale id
class UserNotFoundError(ValidationError):
    """Raised when no user has the given id."""

class UserRepository(ABC):

    @abstractmethod
    def create(self, username, display_name, password, confirmation=None):
        """Validate and store a new user, returning it."""

    @abstractmethod
    def update(self, user_id, username, display_name):
        """Validate and change a user's names, returning the updated user."""

    @abstractmethod
    def find(self, username):
        """Return the matching user, or None."""

    @abstractmethod
    def all_users(self):
        """Every user, oldest first."""

    @abstractmethod
    def authenticate(self, username, password):
        """Return the user when the password is correct, otherwise None."""

    @abstractmethod
    def delete(self, user_id):
        """Remove the user and, by cascade, their decks."""

class SqliteUserRepository(UserRepository):

    def __init__(self, path=USER_DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def create(self, username, display_name, password, confirmation=None):
        problem = check_new_user(username, display_name, password, confirmation)
        if problem:
            raise ValidationError(problem)

        username = username.strip()
        display_name = (display_name or "").strip() or None
        salt, digest = security.hash_password(password)
        created_at = time.time()
        try:
            cursor = self.conn.execute(
                """INSERT INTO users (username, display_name, password_salt,
                                      password_hash, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (username, display_name, salt, digest, created_at),
            )
        except sqlite3.IntegrityError:
            raise DuplicateUserError(f"The username {username!r} is already taken.")
        self.conn.commit()
        return User(username, display_name, salt, digest, created_at, cursor.lastrowid)

    # the password is left alone here; changing it needs the current one checked
    def update(self, user_id, username, display_name):
        problem = check_username(username) or check_display_name(display_name)
        if problem:
            raise ValidationError(problem)

        username = username.strip()
        display_name = (display_name or "").strip() or None
        try:
            cursor = self.conn.execute(
                "UPDATE users SET username = ?, display_name = ? WHERE user_id = ?",
                (username, display_name, user_id),
            )
        except sqlite3.IntegrityError:
            raise DuplicateUserError(f"The username {username!r} is already taken.")
        if cursor.rowcount == 0:
            raise UserNotFoundError("User not found.")
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return self._to_user(row)

    # the database removes the user's decks and their cards through
    # ON DELETE CASCADE, which needs the foreign_keys pragma set in __init__
    def delete(self, user_id):
        cursor = self.conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        self.conn.commit()
        if cursor.rowcount == 0:
            raise UserNotFoundError("User not found.")

    def find(self, username):
        row = self.conn.execute(
            "SELECT * FROM users WHERE username = ? COLLATE NOCASE", ((username or "").strip(),)
        ).fetchone()
        return self._to_user(row) if row else None

    def all_users(self):
        # user_id breaks ties, since two accounts made in the same clock tick
        # would otherwise come back in an unspecified order
        rows = self.conn.execute(
            "SELECT * FROM users ORDER BY created_at, user_id"
        ).fetchall()
        return [self._to_user(row) for row in rows]

    def authenticate(self, username, password):
        user = self.find(username)
        if user is None:
            # hash anyway so a missing user does not answer faster than a
            # wrong password and reveal which usernames exist
            security.hash_password(password or "", security.new_salt())
            return None
        if security.verify_password(password or "", user.password_salt, user.password_hash):
            return user
        return None

    @staticmethod
    def _to_user(row):
        return User(
            row["username"], row["display_name"], row["password_salt"],
            row["password_hash"], row["created_at"], row["user_id"],
        )

    def close(self):
        self.conn.close()
