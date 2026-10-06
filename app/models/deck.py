"""Deck records.

Hold data only. The rules about who may change a deck live in
services/deck_repository.py, so these stay plain descriptions of stored rows.
"""


class Deck:
    def __init__(self, deck_id, user_id, name, created_at, card_count=0):
        self.deck_id = deck_id
        self.user_id = user_id
        self.name = name
        self.created_at = created_at
        self.card_count = card_count  # total copies, so 4 Forests count as 4

    def __repr__(self):
        return f"Deck({self.name!r})"


# one line in a deck: which card and how many copies of it
class DeckEntry:
    def __init__(self, oracle_id, name, quantity):
        self.oracle_id = oracle_id
        self.name = name
        self.quantity = quantity

    def __repr__(self):
        return f"DeckEntry({self.quantity} x {self.name!r})"
