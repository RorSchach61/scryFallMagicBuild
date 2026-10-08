"""The signed-in user's decks and the cards in the selected one.

Owns no storage. Like the other panels it is handed callbacks, so it never
touches a repository and never needs to know who is signed in. The window
refreshes it after any deck change, including ones made from the card pane.
"""
import tkinter as tk
from tkinter import messagebox, ttk

OK_COLOR = "#1a7f37"
ERROR_COLOR = "#b3261e"


class DeckPanel(ttk.Frame):

    def __init__(self, parent, on_list, on_create, on_delete, on_cards, on_remove,
                 on_select=None):
        super().__init__(parent, padding=(12, 12))
        self._on_list = on_list
        self._on_create = on_create
        self._on_delete = on_delete
        self._on_cards = on_cards
        self._on_remove = on_remove
        self._on_select = on_select
        self._decks = []
        self._entries = []
        self._build()

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(1, weight=1)

        # left column: new-deck entry, the deck list, and delete
        new_row = ttk.Frame(self)
        new_row.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        new_row.columnconfigure(0, weight=1)
        self.new_name = tk.StringVar()
        entry = ttk.Entry(new_row, textvariable=self.new_name)
        entry.grid(row=0, column=0, sticky="ew")
        entry.bind("<Return>", lambda _event: self._create())
        ttk.Button(new_row, text="New deck", command=self._create).grid(row=0, column=1, padx=(6, 0))

        self.deck_tree = ttk.Treeview(self, columns=("name", "count"), show="headings",
                                      selectmode="browse")
        self.deck_tree.heading("name", text="Deck")
        self.deck_tree.heading("count", text="Cards")
        self.deck_tree.column("name", width=180, anchor="w")
        self.deck_tree.column("count", width=60, anchor="e")
        self.deck_tree.grid(row=1, column=0, sticky="nsew", padx=(0, 12), pady=(8, 0))
        self.deck_tree.bind("<<TreeviewSelect>>", lambda _event: self._show_cards())

        ttk.Button(self, text="Delete deck", command=self._delete).grid(
            row=2, column=0, sticky="w", pady=(8, 0))

        # right column: what is in the selected deck
        self.deck_title = ttk.Label(self, text="", font=("TkDefaultFont", 11, "bold"))
        self.deck_title.grid(row=0, column=1, sticky="w")

        self.card_tree = ttk.Treeview(self, columns=("qty", "name"), show="headings",
                                      selectmode="browse")
        self.card_tree.heading("qty", text="Qty")
        self.card_tree.heading("name", text="Card")
        self.card_tree.column("qty", width=50, anchor="e")
        self.card_tree.column("name", width=300, anchor="w")
        self.card_tree.grid(row=1, column=1, sticky="nsew", pady=(8, 0))
        self.card_tree.bind("<<TreeviewSelect>>", lambda _event: self._card_selected())

        ttk.Button(self, text="Remove one", command=self._remove).grid(
            row=2, column=1, sticky="w", pady=(8, 0))

        self.message = ttk.Label(self, text="", wraplength=600, justify="left")
        self.message.grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))

    # rows are keyed by oracle_id, so the selection is the id the window needs
    # to look the full card up; rebuilding the list also fires this with an
    # empty selection, which is skipped
    def _card_selected(self):
        selection = self.card_tree.selection()
        if selection and self._on_select is not None:
            self._on_select(selection[0])

    # rebuilds both lists from storage, keeping whichever deck was selected
    def refresh(self):
        selected = self._selected_deck()
        self._decks = self._on_list()
        self.deck_tree.delete(*self.deck_tree.get_children())
        for deck in self._decks:
            self.deck_tree.insert("", "end", iid=str(deck.deck_id),
                                  values=(deck.name, deck.card_count))
        if selected is not None and self.deck_tree.exists(str(selected.deck_id)):
            self.deck_tree.selection_set(str(selected.deck_id))
        self._show_cards()

    def _selected_deck(self):
        selection = self.deck_tree.selection()
        if not selection:
            return None
        deck_id = int(selection[0])
        return next((deck for deck in self._decks if deck.deck_id == deck_id), None)

    # rebuilds (a refresh can rebuild this list more than once)
    def _show_cards(self):
        selected = self.card_tree.selection()
        self.card_tree.delete(*self.card_tree.get_children())
        deck = self._selected_deck()
        if deck is None:
            self._entries = []
            self.deck_title.configure(text="No deck selected")
            return
        self.deck_title.configure(text=f"{deck.name} ({deck.card_count} cards)")
        self._entries = self._on_cards(deck.deck_id)
        for entry in self._entries:
            self.card_tree.insert("", "end", iid=entry.oracle_id, values=(entry.quantity, entry.name))
        if selected and self.card_tree.exists(selected[0]):
            self.card_tree.selection_set(selected[0])

    def _create(self):
        try:
            deck = self._on_create(self.new_name.get())
        except ValueError as exc:
            self._set_message(str(exc), ERROR_COLOR)
            return
        self.new_name.set("")
        self._set_message(f"Created deck {deck.name!r}.", OK_COLOR)
        self.deck_tree.selection_set(str(deck.deck_id))

    def _delete(self):
        deck = self._selected_deck()
        if deck is None:
            self._set_message("Select a deck first.", ERROR_COLOR)
            return
        if not messagebox.askyesno("Delete deck", f"Delete {deck.name!r} and all its cards?",
                                   parent=self):
            return
        self._on_delete(deck.deck_id)
        self._set_message(f"Deleted deck {deck.name!r}.", OK_COLOR)

    def _remove(self):
        deck = self._selected_deck()
        selection = self.card_tree.selection()
        if deck is None or not selection:
            self._set_message("Select a card in the deck first.", ERROR_COLOR)
            return
        self._on_remove(deck.deck_id, selection[0])
        self._set_message("", OK_COLOR)

    def _set_message(self, text, color):
        self.message.configure(text=text, foreground=color)
