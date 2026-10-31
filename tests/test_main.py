import http.client
import sqlite3
import unittest
from unittest import mock

import main
from app.services.json_downloader import FAILED


class LoadCardsTest(unittest.TestCase):

    def test_a_failed_refresh_still_loads_the_saved_cards(self):
        with mock.patch("app.services.json_downloader.ScryfallClient") as client, \
                mock.patch("app.services.json_downloader.log_error"), \
                mock.patch("app.services.json_downloader.ORACLE_CARDS_PATH", mock.Mock()), \
                mock.patch("main.InMemoryCardRepository") as repository:
            client.return_value.get_json_data.side_effect = http.client.IncompleteRead(b"{")
            cards, result = main.load_cards(force=True)
        self.assertIs(cards, repository.load.return_value)
        self.assertEqual(result.status, FAILED)


class StartupErrorTest(unittest.TestCase):

    def setUp(self):
        for name in ("setup_logging", "log_thread_errors", "log_error",
                     "show_startup_error", "start"):
            patcher = mock.patch(f"main.{name}")
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)

    def fail_at_startup(self):
        self.error = sqlite3.OperationalError("unable to open database file")
        self.start.side_effect = self.error
        with self.assertRaises(SystemExit) as caught:
            main.main()
        return caught.exception

    def test_a_clean_start_shows_no_error(self):
        main.main()
        self.show_startup_error.assert_not_called()
        self.log_error.assert_not_called()

    def test_logging_is_ready_before_anything_starts(self):
        calls = mock.Mock()
        calls.attach_mock(self.setup_logging, "setup")
        calls.attach_mock(self.start, "start")
        main.main()
        self.assertEqual([call[0] for call in calls.mock_calls], ["setup", "start"])

    def test_thread_errors_are_logged_from_the_start(self):
        main.main()
        self.log_thread_errors.assert_called_once()

    def test_a_failed_start_is_logged(self):
        self.fail_at_startup()
        self.assertIs(self.log_error.call_args.args[1], self.error)

    def test_a_failed_start_tells_the_user(self):
        self.fail_at_startup()
        self.show_startup_error.assert_called_once()

    def test_a_failed_start_exits_with_an_error_code(self):
        self.assertEqual(self.fail_at_startup().code, 1)


if __name__ == "__main__":
    unittest.main()
