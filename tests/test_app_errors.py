import unittest
from unittest import mock

from app.config import LOG_PATH
from app.gui.app import MagicSearchApp


class CallbackErrorTest(unittest.TestCase):

    def setUp(self):
        # no real window is needed: the handler only uses root as the dialog's parent
        self.app = mock.Mock()
        for name in ("log_error", "messagebox"):
            patcher = mock.patch(f"app.gui.app.{name}")
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)

    def report(self, error):
        MagicSearchApp._on_callback_error(self.app, type(error), error, None)

    def test_logs_the_error(self):
        error = RuntimeError("database is locked")
        self.report(error)
        self.log_error.assert_called_once()
        self.assertIs(self.log_error.call_args.args[1], error)

    def test_tells_the_user(self):
        self.report(RuntimeError("database is locked"))
        self.messagebox.showerror.assert_called_once()

    def test_the_dialog_says_where_the_details_are(self):
        self.report(RuntimeError("database is locked"))
        self.assertIn(str(LOG_PATH), self.messagebox.showerror.call_args.args[1])

    def test_the_dialog_hides_the_raw_error(self):
        self.report(RuntimeError("database is locked"))
        self.assertNotIn("database is locked", self.messagebox.showerror.call_args.args[1])

    def test_logs_before_showing_the_dialog(self):
        # the dialog waits for a click, so the record must already be saved
        calls = mock.Mock()
        calls.attach_mock(self.log_error, "log")
        calls.attach_mock(self.messagebox.showerror, "show")
        self.report(RuntimeError("database is locked"))
        self.assertEqual([call[0] for call in calls.mock_calls], ["log", "show"])


if __name__ == "__main__":
    unittest.main()
