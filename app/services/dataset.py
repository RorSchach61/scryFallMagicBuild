"""Reads the local Scryfall bulk file.

The only module that knows the dataset is gzipped JSONL. Everything above it
sees plain dictionaries, so changing storage format touches this file alone.
"""
import gzip
import json

from app.config import ORACLE_CARDS_PATH


class DatasetMissingError(FileNotFoundError):
    """Raised when the bulk file has not been downloaded yet."""


# scryfall json uses non ascii so utf-8 is needed to read those characters.
# yielded rather than listed so the caller decides what to keep in memory
def read_cards(path=ORACLE_CARDS_PATH):
    if not path.exists():
        raise DatasetMissingError(
            f"{path} not found, run download_oracle_cards() first"
        )
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)
