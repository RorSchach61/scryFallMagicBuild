"""Paths and dataset settings.

Kept in one module so nothing else hardcodes a location, and resolved from this
file rather than the working directory so the app runs from anywhere.
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# a --onefile exe runs from a temp folder deleted on exit, so its data has to
# live in the user's profile instead or accounts and decks would not persist
if getattr(sys, "frozen", False):
    DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / "ScryfallSearch"
else:
    DATA_DIR = PROJECT_ROOT / "data"
ORACLE_CARDS_PATH = DATA_DIR / "oracle_cards.jsonl.gz"
USER_DB_PATH = DATA_DIR / "magic.db"

# scryfall bulk type: one entry per unique card rather than one per printing
BULK_DATASET_TYPE = "oracle_cards"

# scryfall regenerates bulk data on this cadence, so re-downloading sooner
# only burns bandwidth and rate limit
TWELVE_HOURS = 43200

# keys must match scryfall's legalities keys so a deck's format can be passed
# straight to Card.is_legal
FORMATS = (
    ("standard", "Standard"),
    ("pioneer", "Pioneer"),
    ("modern", "Modern"),
    ("legacy", "Legacy"),
    ("vintage", "Vintage"),
    ("pauper", "Pauper"),
    ("commander", "Commander"),
)
