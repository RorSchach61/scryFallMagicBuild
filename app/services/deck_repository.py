"""Deck storage, behind an interface.

Mirrors the user side. Every method takes the owner's user_id and checks it in
the SQL itself, so one account can never read or change another account's decks.
"""
import sqlite3
import time
from abc import ABC, abstractmethod

from app.config import USER_DB_PATH
from app.models.deck import Deck, DeckEntry

DECK_NAME_MAX = 64

# lives in the same database file as users, since decks belong to them
SCHEMA = """
CREATE TABLE IF NOT EXISTS decks (
    deck_id    INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    created_at REAL NOT NULL,
    format     TEXT
);
-- one user cannot have two decks with the same name, but two users can
CREATE UNIQUE INDEX IF NOT EXISTS idx_decks_owner_name ON decks(user_id, name COLLATE NOCASE);

-- card_name is kept beside the id so a deck can be listed before the card
-- dataset has finished loading
CREATE TABLE IF NOT EXISTS deck_cards (
    deck_id   INTEGER NOT NULL REFERENCES decks(deck_id) ON DELETE CASCADE,
    oracle_id TEXT NOT NULL,
    card_name TEXT NOT NULL,
    quantity  INTEGER NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (deck_id, oracle_id)
);
"""


class DeckError(ValueError):
    """Raised when a deck change cannot be made."""


class DuplicateDeckError(DeckError):
    """Raised when the user already has a deck with that name."""


# deliberately the same error for "no such deck" and "not your deck", so
# guessing deck ids reveals nothing about other users
class DeckNotFoundError(DeckError):
    """Raised when the deck does not exist or belongs to someone else."""


class DeckRepository(ABC):

    @abstractmethod
    def create(self, user_id, name):
        """Store a new empty deck for the user, returning it."""

    @abstractmethod
    def decks_for(self, user_id):
        """The user's decks, alphabetical."""

    @abstractmethod
    def delete(self, user_id, deck_id):
        """Remove the deck and every card in it."""

    @abstractmethod
    def set_format(self, user_id, deck_id, format_name):
        """Set the deck's format, or clear it with None."""

    @abstractmethod
    def add_card(self, user_id, deck_id, card, quantity=1):
        """Add copies of a card, stacking onto any already in the deck."""

    @abstractmethod
    def remove_card(self, user_id, deck_id, oracle_id, quantity=1):
        """Remove copies of a card, dropping it once none are left."""

    @abstractmethod
    def cards_in(self, user_id, deck_id):
        """The deck's entries, alphabetical."""


class SqliteDeckRepository(DeckRepository):

    def __init__(self, path=USER_DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # sqlite ignores REFERENCES unless this is switched on, per connection
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self):
        columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(decks)")}
        if "format" not in columns:
            self.conn.execute("ALTER TABLE decks ADD COLUMN format TEXT")

    def create(self, user_id, name):
        name = (name or "").strip()
        if not name:
            raise DeckError("Deck name is required.")
        if len(name) > DECK_NAME_MAX:
            raise DeckError(f"Deck name must be at most {DECK_NAME_MAX} characters.")

        created_at = time.time()
        try:
            cursor = self.conn.execute(
                "INSERT INTO decks (user_id, name, created_at) VALUES (?, ?, ?)",
                (user_id, name, created_at),
            )
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" not in str(exc):
                raise  # e.g. an unknown user_id, which is a bug rather than bad input
            raise DuplicateDeckError(f"You already have a deck named {name!r}.")
        self.conn.commit()
        return Deck(cursor.lastrowid, user_id, name, created_at)

    def decks_for(self, user_id):
        rows = self.conn.execute(
            """SELECT d.deck_id, d.user_id, d.name, d.created_at, d.format,
                      COALESCE(SUM(c.quantity), 0) AS card_count
               FROM decks d
               LEFT JOIN deck_cards c ON c.deck_id = d.deck_id
               WHERE d.user_id = ?
               GROUP BY d.deck_id
               ORDER BY d.name COLLATE NOCASE""",
            (user_id,),
        ).fetchall()
        return [
            Deck(row["deck_id"], row["user_id"], row["name"],
                 row["created_at"], row["card_count"], row["format"])
            for row in rows
        ]

    def delete(self, user_id, deck_id):
        cursor = self.conn.execute(
            "DELETE FROM decks WHERE deck_id = ? AND user_id = ?", (deck_id, user_id)
        )
        self.conn.commit()
        if cursor.rowcount == 0:
            raise DeckNotFoundError("Deck not found.")

    def set_format(self, user_id, deck_id, format_name):
        format_name = (format_name or "").strip().lower() or None
        cursor = self.conn.execute(
            "UPDATE decks SET format = ? WHERE deck_id = ? AND user_id = ?",
            (format_name, deck_id, user_id),
        )
        self.conn.commit()
        if cursor.rowcount == 0:
            raise DeckNotFoundError("Deck not found.")

    def add_card(self, user_id, deck_id, card, quantity=1):
        if quantity < 1:
            raise DeckError("Quantity must be at least 1.")
        if not card.oracle_id:
            raise DeckError(f"{card.name} cannot be added to a deck.")
        self._check_owner(user_id, deck_id)

        # adding a card already in the deck raises its count instead of
        # creating a second row for it
        self.conn.execute(
            """INSERT INTO deck_cards (deck_id, oracle_id, card_name, quantity)
               VALUES (?, ?, ?, ?)
               ON CONFLICT (deck_id, oracle_id)
               DO UPDATE SET quantity = quantity + excluded.quantity""",
            (deck_id, card.oracle_id, card.name, quantity),
        )
        self.conn.commit()

    def remove_card(self, user_id, deck_id, oracle_id, quantity=1):
        if quantity < 1:
            raise DeckError("Quantity must be at least 1.")
        self._check_owner(user_id, deck_id)

        self.conn.execute(
            "DELETE FROM deck_cards WHERE deck_id = ? AND oracle_id = ? AND quantity <= ?",
            (deck_id, oracle_id, quantity),
        )
        self.conn.execute(
            "UPDATE deck_cards SET quantity = quantity - ? WHERE deck_id = ? AND oracle_id = ?",
            (quantity, deck_id, oracle_id),
        )
        self.conn.commit()

    def cards_in(self, user_id, deck_id):
        self._check_owner(user_id, deck_id)
        rows = self.conn.execute(
            """SELECT oracle_id, card_name, quantity FROM deck_cards
               WHERE deck_id = ? ORDER BY card_name COLLATE NOCASE""",
            (deck_id,),
        ).fetchall()
        return [DeckEntry(row["oracle_id"], row["card_name"], row["quantity"]) for row in rows]

    def _check_owner(self, user_id, deck_id):
        row = self.conn.execute(
            "SELECT 1 FROM decks WHERE deck_id = ? AND user_id = ?", (deck_id, user_id)
        ).fetchone()
        if row is None:
            raise DeckNotFoundError("Deck not found.")

    def close(self):
        self.conn.close()
