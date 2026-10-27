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
from app.config import BULK_DATASET_TYPE, ORACLE_CARDS_PATH, TWELVE_HOURS

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


def _find_bulk_entry(client):
    return next((item for item in client.get_json_data()["data"]
                 if item["type"] == BULK_DATASET_TYPE), None)


def _is_current(updated_at):
    return ORACLE_CARDS_PATH.exists() and bool(updated_at) and updated_at == _stored_updated_at()


# after a successful replace the .part is already gone, so the cleanup only
# matters when something failed along the way
def _download_file(url, headers, dest):
    tmp = dest.with_suffix(".part")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=30) as response, open(tmp, "wb") as out:
            expected_size = int(response.headers.get("Content-Length") or 0)
            while chunk := response.read(1024 * 1024):
                out.write(chunk)
        validate_download(tmp, expected_size)
        tmp.replace(dest)
    finally:
        tmp.unlink(missing_ok=True)


def _refresh_from_scryfall(force, report):
    client = ScryfallClient()
    entry = _find_bulk_entry(client)
    if entry is None:
        return DownloadResult(FAILED, "Could not refresh card data: Scryfall did not list it")
    updated_at = entry.get("updated_at")
    if not force and _is_current(updated_at):
        ORACLE_CARDS_PATH.touch()  # restarts the 12 hour wait before asking again
        return DownloadResult(UP_TO_DATE)
    if report:
        report("Downloading card data from Scryfall…")
    _download_file(entry["jsonl_download_uri"], client.headers, ORACLE_CARDS_PATH)
    if updated_at:
        _store_updated_at(updated_at)
    return DownloadResult(DOWNLOADED, "Card data updated from Scryfall")


# Checks if download has happened in recent 12 hours, since scryfall updates bulk
# card data about once a day. force skips that check for a manual refresh, and
# report is told before the large download starts so the window can say so
def download_oracle_cards(force=False, report=None):
    if not force and ORACLE_CARDS_PATH.exists():
        if time.time() - ORACLE_CARDS_PATH.stat().st_mtime < TWELVE_HOURS:
            return DownloadResult(SKIPPED)
    try:
        return _refresh_from_scryfall(force, report)
    except (OSError, KeyError, ValueError) as exc:
        fallback = "using the saved copy" if ORACLE_CARDS_PATH.exists() else "no saved copy yet"
        return DownloadResult(FAILED, f"Could not refresh card data, {fallback} ({exc})")
