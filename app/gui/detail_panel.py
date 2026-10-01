"""Read-only view of a single card."""
import tkinter as tk
from tkinter import ttk

FIELDS = (
    ("Mana cost", lambda card: card.mana_cost or "N/A"),
    ("Type", lambda card: card.type_line or "N/A"),
    ("Power/Toughness", lambda card: card.power_toughness() or "N/A"),
    ("Colors", lambda card: ", ".join(card.colors or []) or "Colorless"),
    ("Color identity", lambda card: ", ".join(card.color_identity or []) or "Colorless"),
    ("Multiverse IDs", lambda card: ", ".join(str(i) for i in card.multiverse_ids or []) or "N/A"),
)


class DetailPanel(ttk.Frame):

    def __init__(self, parent):
        super().__init__(parent, padding=(8, 8))
        self._values = {}
        self._build()
        self.clear()

    def _build(self):
        self.columnconfigure(1, weight=1)

        self.title = ttk.Label(self, text="", font=("TkDefaultFont", 12, "bold"),
                               wraplength=240, justify="left")
        self.title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        # labels stack above their values rather than sitting beside them, so a
        # long type line wraps instead of being clipped by a narrow pane
        for row, (label, _) in enumerate(FIELDS):
            ttk.Label(self, text=label, foreground="gray35").grid(
                row=row * 2 + 1, column=0, sticky="w", pady=(6, 0))
            value = ttk.Label(self, text="", wraplength=240, justify="left")
            value.grid(row=row * 2 + 2, column=0, sticky="w")
            self._values[label] = value

    def show(self, card):
        self.title.configure(text=card.name)
        for label, extract in FIELDS:
            self._values[label].configure(text=extract(card))

    def clear(self):
        self.title.configure(text="No card selected")
        for label, _ in FIELDS:
            self._values[label].configure(text="")
