"""Search box and result table.

Owns no data. It is handed a callback to run searches and reports the selected
card back through another, so it never touches the repository directly.
"""
import tkinter as tk
from tkinter import ttk

DEBOUNCE_MS = 150
RESULT_LIMIT = 200


class SearchPanel(ttk.Frame):

    def __init__(self, parent, on_search, on_select):
        super().__init__(parent, padding=(8, 8))
        self._on_search = on_search
        self._on_select = on_select
        self._pending = None
        self._results = []
        self._build()

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        entry_row = ttk.Frame(self)
        entry_row.grid(row=0, column=0, sticky="ew")
        entry_row.columnconfigure(1, weight=1)

        ttk.Label(entry_row, text="Card name").grid(row=0, column=0, padx=(0, 6))
        self.query = tk.StringVar()
        self.entry = ttk.Entry(entry_row, textvariable=self.query)
        self.entry.grid(row=0, column=1, sticky="ew")
        self.query.trace_add("write", self._on_query_changed)

        columns = ("name", "mana", "type")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")
        for key, heading, width in (
            ("name", "Name", 240), ("mana", "Cost", 90), ("type", "Type", 260)
        ):
            self.tree.heading(key, text=heading)
            self.tree.column(key, width=width, anchor="w")
        self.tree.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.tree.bind("<<TreeviewSelect>>", self._on_row_selected)

        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scroll.grid(row=1, column=1, sticky="ns", pady=(8, 0))
        self.tree.configure(yscrollcommand=scroll.set)

    # typing fires per keystroke, so the search is deferred briefly and any
    # earlier pending search cancelled, leaving one search per pause
    def _on_query_changed(self, *_):
        if self._pending is not None:
            self.after_cancel(self._pending)
        self._pending = self.after(DEBOUNCE_MS, self._run_search)

    def _run_search(self):
        self._pending = None
        self.show_results(self._on_search(self.query.get(), RESULT_LIMIT))

    def show_results(self, cards):
        self._results = cards
        self.tree.delete(*self.tree.get_children())
        for index, card in enumerate(cards):
            self.tree.insert(
                "", "end", iid=str(index),
                values=(card.name, card.mana_cost or "", card.type_line or ""),
            )

    def _on_row_selected(self, _event):
        selection = self.tree.selection()
        if selection:
            self._on_select(self._results[int(selection[0])])

    def focus_entry(self):
        self.entry.focus_set()
