"""Modal window for changing or deleting the signed-in account.

Owns no storage. It is handed callbacks, so it works against any UserRepository
implementation, and never decides whose account it is changing.
"""
import tkinter as tk
from tkinter import messagebox, ttk

from app.gui.user_panel import ERROR_COLOR, OK_COLOR


class AccountWindow(tk.Toplevel):

    def __init__(self, parent, user, on_save, on_check_password, on_delete):
        super().__init__(parent)
        self._on_save = on_save
        self._on_check_password = on_check_password
        self._on_delete = on_delete

        self.title("Edit account")
        self.resizable(False, False)
        self._build(user)

        self.transient(parent)
        self.grab_set()  # modal: the main window cannot be used behind it
        self.lift()
        self.username_entry.focus_set()

    def _build(self, user):
        frame = ttk.Frame(self, padding=(12, 12))
        frame.pack(fill="both", expand=True)
        self._build_details(frame, user).pack(fill="x")
        self._build_delete(frame).pack(fill="x", pady=(12, 0))

    def _build_details(self, parent, user):
        form = ttk.LabelFrame(parent, text="Account details", padding=(12, 8))
        form.columnconfigure(1, weight=1)

        self.username = tk.StringVar(value=user.username)
        self.display_name = tk.StringVar(value=user.display_name or "")

        ttk.Label(form, text="Username").grid(row=0, column=0, sticky="w", pady=4, padx=(0, 8))
        self.username_entry = ttk.Entry(form, textvariable=self.username, width=26)
        self.username_entry.grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(form, text="Display name").grid(row=1, column=0, sticky="w", pady=4, padx=(0, 8))
        ttk.Entry(form, textvariable=self.display_name, width=26).grid(
            row=1, column=1, sticky="ew", pady=4)

        ttk.Button(form, text="Save", command=self._save).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self.save_message = ttk.Label(form, text="", wraplength=280, justify="left")
        self.save_message.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        return form

    def _build_delete(self, parent):
        form = ttk.LabelFrame(parent, text="Delete account", padding=(12, 8))
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Removes this account and all its decks.\nThis cannot be undone.",
                  justify="left").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

        self.password = tk.StringVar()
        ttk.Label(form, text="Password").grid(row=1, column=0, sticky="w", pady=4, padx=(0, 8))
        ttk.Entry(form, textvariable=self.password, width=26, show="•").grid(
            row=1, column=1, sticky="ew", pady=4)

        ttk.Button(form, text="Delete account", command=self._delete).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self.delete_message = ttk.Label(form, text="", wraplength=280, justify="left")
        self.delete_message.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        return form

    def _save(self):
        try:
            user = self._on_save(self.username.get(), self.display_name.get())
        except ValueError as exc:  # validation and duplicate errors
            self.save_message.configure(text=str(exc), foreground=ERROR_COLOR)
        else:
            self.username.set(user.username)
            self.display_name.set(user.display_name or "")
            self.save_message.configure(text=f"Saved as {user.label()}.", foreground=OK_COLOR)

    # the password is checked first, so the final question only appears once
    # the person has proved the account is theirs
    def _delete(self):
        password = self.password.get()
        self.password.set("")
        if not self._on_check_password(password):
            self.delete_message.configure(text="Incorrect password.", foreground=ERROR_COLOR)
            return
        if not messagebox.askyesno(
                "Delete account", "Delete this account and all its decks?\nThis cannot be undone.",
                icon="warning", default="no", parent=self):
            return
        self.destroy()  # releases the grab before the sign-in gate takes it
        self._on_delete()
