"""Create-user form.

Owns no storage. It is handed a callback for creating users, so the same form
works against any UserRepository implementation. It deliberately shows no list
of existing accounts, since that would let anyone enumerate them.
"""
import tkinter as tk
from tkinter import ttk

OK_COLOR = "#1a7f37"
ERROR_COLOR = "#b3261e"


class UserPanel(ttk.Frame):

    def __init__(self, parent, on_create):
        super().__init__(parent, padding=(12, 12))
        self._on_create = on_create
        self._build()

    def _build(self):
        form = ttk.LabelFrame(self, text="New user", padding=(12, 8))
        form.grid(row=0, column=0, sticky="nw")
        form.columnconfigure(1, weight=1)

        self.fields = {}
        rows = (
            ("username", "Username", False),
            ("display_name", "Display name", False),
            ("password", "Password", True),
            ("confirmation", "Confirm password", True),
        )
        for row, (key, label, secret) in enumerate(rows):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
            var = tk.StringVar()
            entry = ttk.Entry(form, textvariable=var, width=26, show="•" if secret else "")
            entry.grid(row=row, column=1, sticky="ew", pady=4)
            self.fields[key] = var

        hint = ttk.Label(form, text="3–32 characters, letters, numbers, _ and -\n"
                                    "Password at least 8 characters",
                         foreground="gray40", justify="left")
        hint.grid(row=len(rows), column=0, columnspan=2, sticky="w", pady=(6, 8))

        buttons = ttk.Frame(form)
        buttons.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="ew")
        self.create_button = ttk.Button(buttons, text="Create user", command=self._submit)
        self.create_button.pack(side="left")
        ttk.Button(buttons, text="Clear", command=self._clear).pack(side="left", padx=(8, 0))

        self.message = ttk.Label(form, text="", wraplength=240, justify="left")
        self.message.grid(row=len(rows) + 2, column=0, columnspan=2, sticky="w", pady=(10, 0))

    def _submit(self):
        values = {key: var.get() for key, var in self.fields.items()}
        self.create_button.configure(state="disabled")
        self._set_message("Creating…", OK_COLOR)
        self.update_idletasks()
        try:
            user = self._on_create(
                values["username"], values["display_name"],
                values["password"], values["confirmation"],
            )
        except ValueError as exc:  # validation and duplicate errors
            self._set_message(str(exc), ERROR_COLOR)
        else:
            self._set_message(f"Created {user.label()}.", OK_COLOR)
            self._clear(keep_message=True)
        finally:
            self.create_button.configure(state="normal")

    def _clear(self, keep_message=False):
        for var in self.fields.values():
            var.set("")
        if not keep_message:
            self._set_message("", OK_COLOR)

    def _set_message(self, text, color):
        self.message.configure(text=text, foreground=color)
