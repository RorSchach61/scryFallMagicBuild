import sqlite3
import unittest
from unittest import mock

from app.gui.deck_panel import ERROR_COLOR, OK_COLOR, DeckPanel
from app.repositories.deck_repository import DeckNotFoundError

GONE = DeckNotFoundError("Deck not found.")


class AttemptTestCase(unittest.TestCase):

    def setUp(self):
        # no real window is needed: only the action and messages are checked
        self.panel = mock.Mock()
        self.panel._attempt = lambda action, *args: DeckPanel._attempt(self.panel, action, *args)
        self.panel._selected_deck.return_value = mock.Mock(deck_id=7)
        self.panel._selected_deck.return_value.name = "Elves"


class AttemptTest(AttemptTestCase):

    def test_success_returns_true(self):
        self.assertTrue(self.panel._attempt(mock.Mock(), 7))

    def test_passes_the_arguments_on(self):
        action = mock.Mock()
        self.panel._attempt(action, 7, "id-forest")
        action.assert_called_once_with(7, "id-forest")

    def test_a_deck_error_returns_false(self):
        self.assertFalse(self.panel._attempt(mock.Mock(side_effect=GONE), 7))

    def test_a_deck_error_shows_in_the_panel(self):
        self.panel._attempt(mock.Mock(side_effect=GONE), 7)
        self.panel._set_message.assert_called_once_with("Deck not found.", ERROR_COLOR)

    def test_a_deck_error_rebuilds_the_stale_list(self):
        self.panel._attempt(mock.Mock(side_effect=GONE), 7)
        self.panel.refresh.assert_called_once()

    def test_a_database_error_reaches_the_window_handler(self):
        with self.assertRaises(sqlite3.OperationalError):
            self.panel._attempt(mock.Mock(side_effect=sqlite3.OperationalError("locked")), 7)
        self.panel._set_message.assert_not_called()


class DeleteTest(AttemptTestCase):

    def setUp(self):
        super().setUp()
        patcher = mock.patch("app.gui.deck_panel.messagebox.askyesno", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_success_is_reported(self):
        DeckPanel._delete(self.panel)
        self.panel._set_message.assert_called_once_with("Deleted deck 'Elves'.", OK_COLOR)

    def test_failure_is_not_reported_as_deleted(self):
        self.panel._on_delete.side_effect = GONE
        DeckPanel._delete(self.panel)
        self.panel._set_message.assert_called_once_with("Deck not found.", ERROR_COLOR)


class RemoveTest(AttemptTestCase):

    def test_success_clears_the_message(self):
        self.panel.card_tree.selection.return_value = ("id-forest",)
        DeckPanel._remove(self.panel)
        self.panel._on_remove.assert_called_once_with(7, "id-forest")
        self.panel._set_message.assert_called_once_with("", OK_COLOR)

    def test_failure_stays_on_screen(self):
        self.panel.card_tree.selection.return_value = ("id-forest",)
        self.panel._on_remove.side_effect = GONE
        DeckPanel._remove(self.panel)
        self.panel._set_message.assert_called_once_with("Deck not found.", ERROR_COLOR)


class FormatTest(AttemptTestCase):

    def test_a_deck_error_shows_in_the_panel(self):
        self.panel.format_choice.current.return_value = 1
        self.panel._on_set_format.side_effect = GONE
        DeckPanel._format_chosen(self.panel)
        self.panel._set_message.assert_called_once_with("Deck not found.", ERROR_COLOR)


if __name__ == "__main__":
    unittest.main()
