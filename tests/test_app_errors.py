import queue
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


class DrainEventsTest(unittest.TestCase):

    def setUp(self):
        self.app = mock.Mock()
        self.app._events = queue.Queue()
        self.repository = mock.Mock()
        self.repository.count.return_value = 5
        self.ready = ("ready", (self.repository, mock.Mock(message="")))

    def drain(self):
        MagicSearchApp._drain_events(self.app)

    def test_keeps_polling_when_the_queue_is_empty(self):
        self.drain()
        self.app.root.after.assert_called_once()

    def test_keeps_polling_after_an_event_fails(self):
        self.app.deck_panel.refresh.side_effect = RuntimeError("database is locked")
        self.app._events.put(self.ready)
        with self.assertRaises(RuntimeError):
            self.drain()
        self.app.root.after.assert_called_once()

    def test_the_failure_still_reaches_the_error_handler(self):
        self.app.deck_panel.refresh.side_effect = RuntimeError("database is locked")
        self.app._events.put(self.ready)
        with self.assertRaisesRegex(RuntimeError, "database is locked"):
            self.drain()

    def test_later_events_are_handled_on_the_next_poll(self):
        self.app.deck_panel.refresh.side_effect = [RuntimeError("database is locked")]
        self.app._events.put(self.ready)
        self.app._events.put(("status", "still working"))
        with self.assertRaises(RuntimeError):
            self.drain()
        self.drain()
        self.app.status.set.assert_called_with("still working")

    def test_a_failed_load_turns_the_refresh_button_back_on(self):
        self.app._events.put(("error", OSError("card file is unreadable")))
        self.drain()
        self.app.refresh_button.configure.assert_called_with(state="normal")


if __name__ == "__main__":
    unittest.main()
