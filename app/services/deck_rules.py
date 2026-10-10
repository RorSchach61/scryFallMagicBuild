"""Format rules for decks.

Pure functions over deck entries and a card lookup, with no storage or widgets,
so the rules can be tested on their own and reused by any caller.
"""


# cards no longer in the dataset are reported as "unknown" rather than skipped,
# since their legality cannot be confirmed
def illegal_entries(format_key, entries, find):
    """Return (entry, status) for every entry not legal in format_key."""
    if not format_key:
        return []
    problems = []
    for entry in entries:
        card = find(entry.oracle_id)
        if card is None:
            problems.append((entry, "unknown"))
        elif not card.is_legal(format_key):
            problems.append((entry, card.legalities.get(format_key, "not_legal")))
    return problems
