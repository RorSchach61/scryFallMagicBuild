"""Keeps the local copy of Scryfall's bulk card file current.

A new file only replaces the old one after it has been checked, so a dropped
connection or an error page can never leave the app with unreadable card data.
Every outcome is returned as a DownloadResult rather than printed, since the
packaged app has no console to print to.
"""
import gzip
import json
import time
import urllib.request

from app.api.scryfall_client import ScryfallClient
from app.config import BULK_DATASET_TYPE, DATA_DIR, ORACLE_CARDS_PATH, TWELVE_HOURS

# a manual refresh downloads ~25 MB, so repeated clicks are held off for a while
REFRESH_COOLDOWN = 5 * 60

SKIPPED, UP_TO_DATE, DOWNLOADED, FAILED = "skipped", "up_to_date", "downloaded", "failed"


class DownloadResult:
    def __init__(self, status, message=""):
        self.status = status
        self.message = message

    def __repr__(self):
        return f"DownloadResult({self.status!r})"


class InvalidDownloadError(ValueError):
    """Raised when a downloaded file is incomplete or not readable."""


# remembers which version of the bulk file is on disk, so an unchanged
# version is never downloaded twice
def _meta_path():
    return ORACLE_CARDS_PATH.with_name(ORACLE_CARDS_PATH.name + ".meta.json")


def _stored_updated_at():
    try:
        return json.loads(_meta_path().read_text(encoding="utf-8")).get("updated_at")
    except (OSError, ValueError, AttributeError):
        return None


def _store_updated_at(updated_at):
    _meta_path().write_text(json.dumps({"updated_at": updated_at}), encoding="utf-8")


# seconds left before another manual refresh is allowed, 0 when it is allowed
def cooldown_remaining(last_refresh, now=None):
    if last_refresh is None:
        return 0
    now = time.time() if now is None else now
    return max(0, REFRESH_COOLDOWN - (now - last_refresh))


# the size the server announced catches a cut-off transfer, and reading the gzip
# to its end catches anything else that isn't a complete gzip file
def validate_download(path, expected_size=None):
    actual = path.stat().st_size
    if expected_size and actual != expected_size:
        raise InvalidDownloadError(f"expected {expected_size:,} bytes, got {actual:,}")
    try:
        with gzip.open(path, "rb") as f:
            while f.read(1024 * 1024):
                pass
    except (OSError, EOFError) as exc:
        raise InvalidDownloadError(f"file is not readable ({exc})") from exc


# Checks if download has happened in recent 12 hours, since scryfall updates bulk
# card data about once a day. force skips that check for a manual refresh, and
# report is told before the large download starts so the window can say so
def download_oracle_cards(force=False, report=None):
    if not force and ORACLE_CARDS_PATH.exists():
        if time.time() - ORACLE_CARDS_PATH.stat().st_mtime < TWELVE_HOURS:
            return DownloadResult(SKIPPED)

    # a failed refresh is not fatal: an older file still works, and a missing
    # one is reported by dataset.py once the window is up
    tmp = ORACLE_CARDS_PATH.with_suffix(".part")
    try:
        client = ScryfallClient()
        entry = next((item for item in client.get_json_data()["data"]
                      if item["type"] == BULK_DATASET_TYPE), None)
        if entry is None:
            return DownloadResult(FAILED, "Could not refresh card data: Scryfall did not list it")

        updated_at = entry.get("updated_at")
        if not force and ORACLE_CARDS_PATH.exists() and updated_at \
                and updated_at == _stored_updated_at():
            ORACLE_CARDS_PATH.touch()  # restarts the 12 hour wait before asking again
            return DownloadResult(UP_TO_DATE)

        if report:
            report("Downloading card data from Scryfall…")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(entry["jsonl_download_uri"], headers=client.headers)
        with urllib.request.urlopen(request, timeout=30) as response, open(tmp, "wb") as out:
            expected_size = int(response.headers.get("Content-Length") or 0)
            while chunk := response.read(1024 * 1024):
                out.write(chunk)
        validate_download(tmp, expected_size)
        tmp.replace(ORACLE_CARDS_PATH)
        if updated_at:
            _store_updated_at(updated_at)
        return DownloadResult(DOWNLOADED, "Card data updated from Scryfall")
    except (OSError, KeyError, ValueError) as exc:
        tmp.unlink(missing_ok=True)
        fallback = "using the saved copy" if ORACLE_CARDS_PATH.exists() else "no saved copy yet"
        return DownloadResult(FAILED, f"Could not refresh card data, {fallback} ({exc})")
