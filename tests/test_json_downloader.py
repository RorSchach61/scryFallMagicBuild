import copy
import gzip
import io
import json
import os
import tempfile
import time
import unittest
import zlib
from pathlib import Path
from unittest import mock

from app.services.json_downloader import (
    DOWNLOADED, FAILED, SKIPPED, UP_TO_DATE, REFRESH_COOLDOWN,
    InvalidDownloadError, cooldown_remaining, download_oracle_cards, validate_download,
)

BULK_LIST = {"data": [{
    "type": "oracle_cards",
    "updated_at": "2026-10-21T09:00:00+00:00",
    "jsonl_download_uri": "https://data.scryfall.io/oracle-cards.jsonl.gz",
}]}


def gzipped(text):
    return gzip.compress(text.encode("utf-8"))


def card_file(*names):
    lines = (json.dumps({"object": "card", "name": name}) for name in names)
    return gzipped("\n".join(lines) + "\n")


# stands in for urlopen's response: a file-like body plus its headers
class FakeResponse(io.BytesIO):
    def __init__(self, body, content_length=None):
        super().__init__(body)
        length = len(body) if content_length is None else content_length
        self.headers = {"Content-Length": str(length)}


class DownloaderTestCase(unittest.TestCase):

    def setUp(self):
        # point the downloader at an empty temp folder so the real card file
        # is never touched and the freshness check never skips the download
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name) / "oracle_cards.jsonl.gz"
        patcher = mock.patch("app.services.json_downloader.ORACLE_CARDS_PATH", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

        client = mock.patch("app.services.json_downloader.ScryfallClient")
        self.client = client.start().return_value
        self.addCleanup(client.stop)
        self.client.get_json_data.return_value = BULK_LIST
        self.client.headers = {"User-Agent": "test"}

        urlopen = mock.patch("app.services.json_downloader.urllib.request.urlopen")
        self.urlopen = urlopen.start()
        self.addCleanup(urlopen.stop)

        # the small files here stand in for the real 39,000 card download
        minimum = mock.patch("app.services.json_downloader.MIN_CARD_COUNT", 1)
        minimum.start()
        self.addCleanup(minimum.stop)

    def list_size(self, size):
        listing = copy.deepcopy(BULK_LIST)
        listing["data"][0]["compressed_size"] = size
        self.client.get_json_data.return_value = listing

    def old_file_text(self):
        with gzip.open(self.path, "rt") as f:
            return f.read()

    def serve(self, body, content_length=None):
        self.urlopen.return_value = FakeResponse(body, content_length)

    def write_old_file(self, age=0):
        self.path.write_bytes(gzipped('{"name": "Old"}\n'))
        stamp = time.time() - age
        os.utime(self.path, (stamp, stamp))


class DownloadFailureTest(DownloaderTestCase):

    def test_timeout_does_not_crash(self):
        self.client.get_json_data.side_effect = TimeoutError
        result = download_oracle_cards()
        self.assertEqual(result.status, FAILED)
        self.assertIn("no saved copy", result.message)

    def test_truncated_download_keeps_the_old_file(self):
        self.write_old_file(age=24 * 3600)
        body = card_file("New")
        self.serve(body, content_length=len(body) + 100)
        result = download_oracle_cards()
        self.assertEqual(result.status, FAILED)
        self.assertIn("saved copy", result.message)
        with gzip.open(self.path, "rt") as f:
            self.assertIn("Old", f.read())

    def test_corrupt_download_keeps_the_old_file(self):
        self.write_old_file(age=24 * 3600)
        self.serve(b"<html>not a gzip file</html>")
        self.assertEqual(download_oracle_cards().status, FAILED)
        with gzip.open(self.path, "rt") as f:
            self.assertIn("Old", f.read())

    def test_failed_download_leaves_no_part_file(self):
        self.serve(b"garbage")
        download_oracle_cards()
        self.assertEqual(list(self.path.parent.iterdir()), [])

    def test_gzipped_error_page_keeps_the_old_file(self):
        self.write_old_file(age=24 * 3600)
        self.serve(gzipped("<html>503 Service Unavailable</html>\n"))
        self.assertEqual(download_oracle_cards().status, FAILED)
        self.assertIn("Old", self.old_file_text())

    def test_empty_gzip_keeps_the_old_file(self):
        self.write_old_file(age=24 * 3600)
        self.serve(gzipped(""))
        self.assertEqual(download_oracle_cards().status, FAILED)
        self.assertIn("Old", self.old_file_text())

    def test_wrong_size_from_scryfalls_list_keeps_the_old_file(self):
        # its own Content-Length is correct, so only the listed size can catch it
        self.write_old_file(age=24 * 3600)
        body = card_file("New")
        self.list_size(len(body) + 100)
        self.serve(body)
        self.assertEqual(download_oracle_cards().status, FAILED)
        self.assertIn("Old", self.old_file_text())

    def test_a_rejected_download_is_tried_again_next_time(self):
        self.serve(gzipped("<html>503</html>\n"))
        download_oracle_cards()
        self.urlopen.reset_mock()
        self.serve(card_file("New"))
        self.assertEqual(download_oracle_cards().status, DOWNLOADED)


class DownloadSuccessTest(DownloaderTestCase):

    def test_valid_download_replaces_the_file(self):
        self.write_old_file(age=24 * 3600)
        self.serve(card_file("New"))
        result = download_oracle_cards()
        self.assertEqual(result.status, DOWNLOADED)
        with gzip.open(self.path, "rt") as f:
            self.assertIn("New", f.read())

    def test_a_matching_listed_size_is_accepted(self):
        body = card_file("New")
        self.list_size(len(body))
        self.serve(body)
        self.assertEqual(download_oracle_cards().status, DOWNLOADED)

    def test_download_sends_the_client_headers(self):
        self.serve(card_file("New"))
        download_oracle_cards()
        request = self.urlopen.call_args.args[0]
        self.assertEqual(request.get_header("User-agent"), "test")

    def test_report_is_told_before_downloading(self):
        self.serve(card_file("New"))
        report = mock.Mock()
        download_oracle_cards(report=report)
        report.assert_called_once()


class DownloadSkipTest(DownloaderTestCase):

    def test_recent_file_skips_without_asking_scryfall(self):
        self.write_old_file(age=60)
        self.assertEqual(download_oracle_cards().status, SKIPPED)
        self.client.get_json_data.assert_not_called()

    def test_unchanged_data_is_not_downloaded_again(self):
        self.serve(card_file("New"))
        download_oracle_cards()
        os.utime(self.path, (time.time() - 24 * 3600,) * 2)
        self.urlopen.reset_mock()
        self.assertEqual(download_oracle_cards().status, UP_TO_DATE)
        self.urlopen.assert_not_called()

    def test_force_downloads_even_when_recent_and_unchanged(self):
        self.serve(card_file("New"))
        download_oracle_cards()
        self.serve(card_file("New"))
        self.assertEqual(download_oracle_cards(force=True).status, DOWNLOADED)


class ValidateDownloadTest(DownloaderTestCase):

    def assert_rejected(self, body):
        self.path.write_bytes(body)
        with self.assertRaises(InvalidDownloadError):
            validate_download(self.path)

    def test_real_card_data_is_accepted(self):
        self.path.write_bytes(card_file("Forest", "Island"))
        validate_download(self.path)

    def test_blank_lines_are_ignored(self):
        self.path.write_bytes(gzipped('{"object": "card", "name": "Forest"}\n\n'))
        validate_download(self.path)

    def test_size_mismatch_is_rejected(self):
        self.path.write_bytes(card_file("Forest"))
        with self.assertRaises(InvalidDownloadError):
            validate_download(self.path, expected_size=1)

    def test_unknown_size_still_checks_the_gzip(self):
        self.assert_rejected(card_file("Forest")[:-4])

    def test_html_is_rejected(self):
        self.assert_rejected(gzipped("<html>503 Service Unavailable</html>\n"))

    def test_a_scryfall_error_object_is_rejected(self):
        self.assert_rejected(gzipped('{"object": "error", "status": 503}\n'))

    def test_json_that_is_not_an_object_is_rejected(self):
        self.assert_rejected(gzipped('["Forest"]\n'))

    def test_a_card_without_a_name_is_rejected(self):
        self.assert_rejected(gzipped('{"object": "card"}\n'))

    def test_one_bad_line_among_good_cards_is_rejected(self):
        self.assert_rejected(gzipped(
            '{"object": "card", "name": "Forest"}\n{"object": "error"}\n'))

    def test_invalid_utf8_is_rejected(self):
        self.assert_rejected(gzip.compress(b'{"object": "card", "name": "\xff"}\n'))

    def test_an_empty_file_is_rejected(self):
        self.assert_rejected(gzipped(""))

    def test_too_few_cards_are_rejected(self):
        with mock.patch("app.services.json_downloader.MIN_CARD_COUNT", 3):
            self.assert_rejected(card_file("Forest", "Island"))

    def test_the_minimum_itself_is_accepted(self):
        self.path.write_bytes(card_file("Forest", "Island", "Swamp"))
        with mock.patch("app.services.json_downloader.MIN_CARD_COUNT", 3):
            validate_download(self.path)

    def test_a_zlib_error_is_a_rejection(self):
        self.path.write_bytes(card_file("Forest"))
        with mock.patch("app.services.json_downloader.read_cards",
                        side_effect=zlib.error("invalid distance too far back")):
            with self.assertRaises(InvalidDownloadError):
                validate_download(self.path)


class CooldownTest(unittest.TestCase):

    def test_never_refreshed_is_allowed(self):
        self.assertEqual(cooldown_remaining(None), 0)

    def test_just_refreshed_waits_the_full_cooldown(self):
        self.assertEqual(cooldown_remaining(1000, now=1000), REFRESH_COOLDOWN)

    def test_cooldown_ends(self):
        self.assertEqual(cooldown_remaining(1000, now=1000 + REFRESH_COOLDOWN + 1), 0)


if __name__ == "__main__":
    unittest.main()
