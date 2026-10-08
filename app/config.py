"""Paths and dataset settings.

Kept in one module so nothing else hardcodes a location, and resolved from this
file rather than the working directory so the app runs from anywhere.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
ORACLE_CARDS_PATH = DATA_DIR / "oracle_cards.jsonl.gz"
USER_DB_PATH = DATA_DIR / "magic.db"

# scryfall bulk type: one entry per unique card rather than one per printing
BULK_DATASET_TYPE = "oracle_cards"

# scryfall regenerates bulk data on this cadence, so re-downloading sooner
# only burns bandwidth and rate limit
TWELVE_HOURS = 43200
