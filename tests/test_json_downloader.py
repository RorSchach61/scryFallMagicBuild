import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.services.json_downloader import download_oracle_cards


class DownloadFailureTest(unittest.TestCase):

    def setUp(self):
        # point the downloader at an empty temp folder so the real card file
        # is never touched and the freshness check never skips the download
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        data_dir = Path(self.dir.name)
        for name, value in (("DATA_DIR", data_dir),
                            ("ORACLE_CARDS_PATH", data_dir / "oracle_cards.jsonl.gz")):
            patcher = mock.patch(f"app.services.json_downloader.{name}", value)
            patcher.start()
            self.addCleanup(patcher.stop)

    @mock.patch("app.services.json_downloader.ScryfallClient")
    def test_timeout_does_not_crash(self, fake_client):
        fake_client.return_value.get_json_data.side_effect = TimeoutError
        download_oracle_cards()


if __name__ == "__main__":
    unittest.main()
