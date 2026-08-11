"""Card lookup, behind an interface.

Callers depend on CardRepository, never on how cards are stored. The in-memory
implementation reads the dataset once at startup because re-parsing it per
search costs seconds; a database-backed version can replace it without any
change above this layer.
"""
from abc import ABC, abstractmethod

from app.models.card import Card
from app.services.dataset import read_cards
from app.services.searchCards import cardSearch


class CardRepository(ABC):

    @abstractmethod
    def search(self, term, limit=None):
        """Return cards whose name contains term, best matches first."""

    @abstractmethod
    def count(self):
        """Total cards available."""


class InMemoryCardRepository(CardRepository):

    def __init__(self, cards):
        self._cards = list(cards)

    # names are matched far more often than they are built, so the lowered
    # form is cached alongside each card rather than recomputed per search
    @classmethod
    def load(cls, progress=None):
        cards = []
        for i, raw in enumerate(read_cards()):
            cards.append(Card.create_from_json(raw))
            if progress and i % 5000 == 0:
                progress(i)
        return cls(cards)

    def search(self, term, limit=None):
        term = cardSearch.normalize(term)
        if not term:
            return []
        found = [card for card in self._cards if term in card.name.lower()]
        found.sort(key=lambda card: cardSearch.sortKey(card.name, term))
        return found[:limit] if limit else found

    def count(self):
        return len(self._cards)
