"""User storage, behind an interface.

The app is single-user, so this only creates and lists the account that owns
the decks. The table keeps its old password columns because databases made
while the app had a sign-in screen still have them marked NOT NULL.
"""
import time
from abc import ABC, abstractmethod
from app.config import USER_DB_PATH
from app.db.connection import connect
from app.models.user import User

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

class UserRepository(ABC):

    @abstractmethod
    def create(self, username):
        """Store a new user, returning it."""

    @abstractmethod
    def all_users(self):
        """Every user, oldest first."""

class SqliteUserRepository(UserRepository):

    def __init__(self, path=USER_DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        with connect(path) as conn:
            conn.executescript(SCHEMA)

    # nothing signs in any more, so the password columns are filled with
    # empty strings only to satisfy their NOT NULL constraint
    def create(self, username):
        created_at = time.time()
        with connect(self._path) as conn:
            cursor = conn.execute(
                """INSERT INTO users (username, password_salt, password_hash, created_at)
                   VALUES (?, '', '', ?)""",
                (username, created_at),
            )
        return User(username, created_at, cursor.lastrowid)

    def all_users(self):
        # user_id breaks ties, since two accounts made in the same clock tick
        # would otherwise come back in an unspecified order
        with connect(self._path) as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY created_at, user_id").fetchall()
        return [User(row["username"], row["created_at"], row["user_id"]) for row in rows]
