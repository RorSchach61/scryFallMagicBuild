"""Modal sign-in gate.

Shown before the main window, and again after signing out. Offers account
creation alongside sign-in because on a fresh install there is nobody to sign
in as yet.
"""
import tkinter as tk
from tkinter import ttk

from app.gui.user_panel import UserPanel

ERROR_COLOR = "#b3261e"

# deliberately vague: saying "no such user" would let anyone test whether a
# given account exists
FAILURE_MESSAGE = "Incorrect username or password."


class LoginWindow(tk.Toplevel):

    def __init__(self, parent, session, on_create):
        super().__init__(parent)
        self._session = session
        self._on_create = on_create

        self.title("Sign in")
        self.resizable(False, False)
        self._build()

        # deliberately not self.transient(parent): on Windows, a Toplevel
        # transient to a withdrawn owner can fail to ever be mapped to a
        # visible window, leaving the whole app invisible with no error.
        # grab_set() alone is enough to keep this modal.
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.grab_set()  # modal: the main window cannot be used behind it
        self.lift()
        self.username.focus_set()

    def _build(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        notebook.add(self._build_signin(notebook), text="Sign in")
        notebook.add(
            UserPanel(notebook, on_create=self._create_and_sign_in),
            text="Create account",
        )

    def _build_signin(self, parent):
        frame = ttk.Frame(parent, padding=(16, 16))
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Username").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.username = ttk.Entry(frame, width=26)
        self.username.grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(frame, text="Password").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        self.password = ttk.Entry(frame, width=26, show="•")
        self.password.grid(row=1, column=1, sticky="ew", pady=4)

        self.sign_in_button = ttk.Button(frame, text="Sign in", command=self._submit)
        self.sign_in_button.grid(row=2, column=0, columnspan=2, sticky="w", pady=(12, 0))

        self.message = ttk.Label(frame, text="", foreground=ERROR_COLOR, wraplength=240)
        self.message.grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))

        for widget in (self.username, self.password):
            widget.bind("<Return>", lambda _event: self._submit())
        return frame

    def _submit(self):
        self.sign_in_button.configure(state="disabled")
        self.update_idletasks()
        try:
            user = self._session.login(self.username.get(), self.password.get())
        finally:
            self.sign_in_button.configure(state="normal")

        if user is None:
            self.message.configure(text=FAILURE_MESSAGE)
            self.password.delete(0, "end")
            self.password.focus_set()
        else:
            self.destroy()

    # creating an account signs that account straight in, so the gate is not
    # shown twice in a row
    def _create_and_sign_in(self, username, display_name, password, confirmation):
        user = self._on_create(username, display_name, password, confirmation)
        self._session.login(username, password)
        self.after(400, self.destroy)  # leaves the confirmation briefly visible
        return user

    def _cancel(self):
        self.destroy()
