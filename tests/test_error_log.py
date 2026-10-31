import logging
import tempfile
import unittest
from pathlib import Path

from app.utils.error_log import (
    LOGGER_NAME, MAX_LOG_BYTES, close_logging, log_error, setup_logging)


def failed_error():
    try:
        raise RuntimeError("the database went away")
    except RuntimeError as exc:
        return exc


class ErrorLogTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.addCleanup(close_logging)  # windows cannot delete an open log
        self.path = Path(self.dir.name) / "logs" / "app.log"
        setup_logging(self.path)

    def log_text(self):
        return self.path.read_text(encoding="utf-8")

    def test_writes_the_message(self):
        log_error("Could not delete deck", failed_error())
        self.assertIn("Could not delete deck", self.log_text())

    def test_writes_the_traceback(self):
        log_error("Could not delete deck", failed_error())
        text = self.log_text()
        self.assertIn("RuntimeError: the database went away", text)
        self.assertIn("failed_error", text)

    def test_creates_the_folder(self):
        log_error("Could not delete deck", failed_error())
        self.assertTrue(self.path.parent.is_dir())

    def test_no_file_until_something_is_logged(self):
        self.assertFalse(self.path.exists())

    def test_keeps_earlier_errors(self):
        log_error("first", failed_error())
        log_error("second", failed_error())
        text = self.log_text()
        self.assertIn("first", text)
        self.assertIn("second", text)

    def test_setting_up_twice_does_not_write_twice(self):
        setup_logging(self.path)
        log_error("only once", failed_error())
        self.assertEqual(self.log_text().count("only once"), 1)

    def test_an_error_that_was_never_raised_can_be_logged(self):
        log_error("not raised", ValueError("no traceback"))
        self.assertIn("ValueError: no traceback", self.log_text())

    def test_old_entries_roll_into_a_backup(self):
        log_error("x" * (MAX_LOG_BYTES + 1), failed_error())
        log_error("newest", failed_error())
        self.assertTrue(self.path.with_name("app.log.1").exists())
        self.assertIn("newest", self.log_text())

    def test_does_not_write_to_the_console(self):
        self.assertFalse(logging.getLogger(LOGGER_NAME).propagate)


class UnusableLogTest(unittest.TestCase):

    def test_a_folder_that_cannot_be_made_does_not_stop_startup(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.addCleanup(close_logging)
        blocker = Path(directory.name) / "not_a_folder"
        blocker.write_text("a file is in the way", encoding="utf-8")

        setup_logging(blocker / "app.log")
        log_error("nowhere to go", failed_error())


if __name__ == "__main__":
    unittest.main()
