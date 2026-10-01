"""Name matching and result ordering.

Pure functions over strings, no file access and no card objects, so the rules
can be tested on their own and reused by any caller.
"""


class cardSearch:

    EXACT, PREFIX, WORD_START, CONTAINS = 0, 1, 2, 3

    @staticmethod
    def normalize(text):
        return (text or "").strip().lower()

    @staticmethod
    def matches(name, term):
        return cardSearch.normalize(term) in cardSearch.normalize(name)

    # a search for "forest" should surface Forest before Deep Forest Hermit,
    # so matches are bucketed by how closely they align before sorting
    @staticmethod
    def rank(name, term):
        name, term = cardSearch.normalize(name), cardSearch.normalize(term)
        if name == term:
            return cardSearch.EXACT
        if name.startswith(term):
            return cardSearch.PREFIX
        if any(word.startswith(term) for word in name.replace("//", " ").split()):
            return cardSearch.WORD_START
        return cardSearch.CONTAINS

    # ties inside a bucket fall back to shorter name, then alphabetical
    @staticmethod
    def sortKey(name, term):
        return (cardSearch.rank(name, term), len(name), cardSearch.normalize(name))
