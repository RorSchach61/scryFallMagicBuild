import gzip
import io
import os
import tempfile
import time
import unittest
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
        data_dir = Path(self.dir.name)
        self.path = data_dir / "oracle_cards.jsonl.gz"
        for name, value in (("DATA_DIR", data_dir), ("ORACLE_CARDS_PATH", self.path)):
            patcher = mock.patch(f"app.services.json_downloader.{name}", value)
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
        body = gzipped('{"name": "New"}\n')
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


class DownloadSuccessTest(DownloaderTestCase):

    def test_valid_download_replaces_the_file(self):
        self.write_old_file(age=24 * 3600)
        self.serve(gzipped('{"name": "New"}\n'))
        result = download_oracle_cards()
        self.assertEqual(result.status, DOWNLOADED)
        with gzip.open(self.path, "rt") as f:
            self.assertIn("New", f.read())

    def test_download_sends_the_client_headers(self):
        self.serve(gzipped("{}\n"))
        download_oracle_cards()
        request = self.urlopen.call_args.args[0]
        self.assertEqual(request.get_header("User-agent"), "test")

    def test_report_is_told_before_downloading(self):
        self.serve(gzipped("{}\n"))
        report = mock.Mock()
        download_oracle_cards(report=report)
        report.assert_called_once()


class DownloadSkipTest(DownloaderTestCase):

    def test_recent_file_skips_without_asking_scryfall(self):
        self.write_old_file(age=60)
        self.assertEqual(download_oracle_cards().status, SKIPPED)
        self.client.get_json_data.assert_not_called()

    def test_unchanged_data_is_not_downloaded_again(self):
        self.serve(gzipped("{}\n"))
        download_oracle_cards()
        os.utime(self.path, (time.time() - 24 * 3600,) * 2)
        self.urlopen.reset_mock()
        self.assertEqual(download_oracle_cards().status, UP_TO_DATE)
        self.urlopen.assert_not_called()

    def test_force_downloads_even_when_recent_and_unchanged(self):
        self.serve(gzipped("{}\n"))
        download_oracle_cards()
        self.serve(gzipped("{}\n"))
        self.assertEqual(download_oracle_cards(force=True).status, DOWNLOADED)


class ValidateDownloadTest(DownloaderTestCase):

    def test_size_mismatch_is_rejected(self):
        self.path.write_bytes(gzipped("{}\n"))
        with self.assertRaises(InvalidDownloadError):
            validate_download(self.path, expected_size=1)

    def test_unknown_size_still_checks_the_gzip(self):
        self.path.write_bytes(gzipped("{}\n")[:-4])
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
